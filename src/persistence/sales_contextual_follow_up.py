"""Outbound sales follow-up after a pause (spec section 13).

Sweeps QUALIFYING/CONTACTED/NEW_LEAD cases that already have a sales reason
(OBJECTION_DEFERRED or CALLBACK_REQUESTED), phrases SEND_CONTEXTUAL_FOLLOW_UP,
and delivers SMS when consent/STOP/quiet hours allow it.

Does not change ProcessState, does not qualify, does not create CRM. If there
is no outbound channel, nothing is recorded as sent — the engine already
recorded the follow-up window from SCHEDULE_CALLBACK.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from src.ai.errors import AIInvalidOutputError, AIProviderError
from src.domain.conversations import (
    ConversationStatus,
    ConversationMessage,
    MessageDirection,
    MessageRole,
)
from src.domain.events import EventType
from src.domain.models import ProcessEvent
from src.domain.sales import (
    CustomerSalesProfile,
    FollowUpReason,
    ObjectionStatus,
    SalesMove,
    SalesStage,
)
from src.domain.states import ProcessState
from src.engine.sales_contextual_follow_up import (
    ContextualFollowUpDecision,
    ContextualFollowUpSnapshot,
    ELIGIBLE_PROCESS_STATES,
    cadence_from_config,
    decide_contextual_follow_up,
    phrase_contextual_follow_up,
    timezone_from_sources,
)
from src.engine.sales_live_turn import listed_business_facts
from src.engine.sales_response_validator import (
    SalesPolicyValidator,
    SalesResponseCandidate,
    SalesResponseValidationContext,
)
from src.persistence.errors import StaleCaseError, StaleSalesProfileError
from src.persistence.repositories import DeliveryStatus, UnitOfWorkFactory
from src.persistence.sms_service import SmsService

LOGGER = logging.getLogger("uvicorn.error")

_ELIGIBLE_STATES = tuple(ELIGIBLE_PROCESS_STATES)
_HUMAN_OWNED = frozenset({
    ConversationStatus.HUMAN_TAKEOVER_REQUESTED,
    ConversationStatus.HUMAN_TAKEOVER_ACTIVE,
})
_NO_CHANNEL_CODES = frozenset({"no_sms_consent", "no_phone", "sms_suppressed"})


@dataclass(frozen=True, slots=True)
class SalesContextualFollowUpSweepResult:
    businesses_scanned: int
    cases_considered: int
    follow_ups_sent: int
    follow_ups_skipped_no_channel: int
    follow_ups_skipped_stale: int


class PersistentSalesContextualFollowUpRunner:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        sms_service: SmsService,
        response_generator: Any | None = None,
        validator: SalesPolicyValidator | None = None,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self.sms_service = sms_service
        self._generator = response_generator
        self._validator = validator or SalesPolicyValidator()

    def run(self, now: datetime) -> SalesContextualFollowUpSweepResult:
        with self.unit_of_work_factory() as uow:
            businesses = uow.businesses.list_all()
        cases_considered = 0
        follow_ups_sent = 0
        skipped_no_channel = 0
        skipped_stale = 0
        for business in businesses:
            sent, considered, no_channel, stale = self._sweep_business(
                business.business_id, now,
            )
            cases_considered += considered
            follow_ups_sent += sent
            skipped_no_channel += no_channel
            skipped_stale += stale
        _log_event(
            logging.INFO,
            "sales_contextual_follow_up_sweep_completed",
            businesses_scanned=len(businesses),
            cases_considered=cases_considered,
            follow_ups_sent=follow_ups_sent,
            follow_ups_skipped_no_channel=skipped_no_channel,
            follow_ups_skipped_stale=skipped_stale,
        )
        return SalesContextualFollowUpSweepResult(
            len(businesses),
            cases_considered,
            follow_ups_sent,
            skipped_no_channel,
            skipped_stale,
        )

    def _sweep_business(self, business_id: str, now: datetime) -> tuple[int, int, int, int]:
        with self.unit_of_work_factory() as uow:
            dna_version = uow.business_dna.get_active(business_id)
            if dna_version is None:
                return 0, 0, 0, 0
            if not self.sms_service.configured or self.sms_service.get_number(business_id) is None:
                return 0, 0, 0, 0
            cases = uow.cases.list_by_state(business_id, _ELIGIBLE_STATES)

        sent = 0
        considered = 0
        no_channel = 0
        stale = 0
        for case in cases:
            considered += 1
            outcome = self._send_one(business_id, case.case_id, now)
            if outcome == "sent":
                sent += 1
            elif outcome == "no_channel":
                no_channel += 1
            elif outcome == "stale":
                stale += 1
        return sent, considered, no_channel, stale

    def _send_one(self, business_id: str, case_id: str, now: datetime) -> str:
        with self.unit_of_work_factory() as uow:
            prepared = self._prepare(uow, business_id, case_id, now)
            if prepared is None:
                return "gone"
            decision, snapshot, message_text, dna, profile = prepared
            if decision.skip_code in _NO_CHANNEL_CODES:
                uow.commit()
                return "no_channel"
            if not decision.due or not decision.sendable or decision.delivery_attempt_number is None:
                uow.commit()
                return "not_due"
            attempt, owns_send = uow.follow_up_deliveries.claim_attempt(
                business_id,
                case_id,
                decision.delivery_attempt_number,
                message_text=message_text,
                now=now,
            )
            uow.commit()

        if not owns_send:
            if attempt.status == DeliveryStatus.SENT:
                delivered, twilio_sid = True, attempt.twilio_sid
            elif attempt.status == DeliveryStatus.FAILED:
                delivered, twilio_sid = False, None
            else:
                return "already_claimed"
        else:
            dispatched = self._authorize_and_dispatch(
                business_id,
                case_id,
                decision.delivery_attempt_number,
                now,
                attempt.message_text,
            )
            if dispatched is None:
                return "not_due"
            delivered, twilio_sid = dispatched

        return self._record_outcome_if_still_due(
            business_id,
            case_id,
            decision,
            now,
            attempt.message_text,
            delivered,
            twilio_sid,
        )

    def _authorize_and_dispatch(
        self,
        business_id: str,
        case_id: str,
        delivery_attempt_number: int,
        now: datetime,
        message_text: str,
    ) -> tuple[bool, str | None] | None:
        with self.unit_of_work_factory() as uow:
            prepared = self._prepare(uow, business_id, case_id, now, for_update=True)
            if prepared is None:
                return None
            decision, snapshot, _text, _dna, _profile = prepared
            if (
                not decision.due
                or not decision.sendable
                or decision.delivery_attempt_number != delivery_attempt_number
                or not snapshot.has_phone
            ):
                return None
            case = uow.cases.get(business_id, case_id, for_update=True)
            if case is None or not case.lead.phone:
                return None
            if self.sms_service.is_suppressed(business_id, case.lead.phone):
                return None
            twilio_sid = self.sms_service.send_outbound(
                business_id, to_number=case.lead.phone, body=message_text,
            )
            delivered = twilio_sid is not None
            uow.follow_up_deliveries.mark_result(
                business_id,
                case_id,
                delivery_attempt_number,
                sent=delivered,
                twilio_sid=twilio_sid,
                now=now,
            )
            uow.commit()
            return delivered, twilio_sid

    def _record_outcome_if_still_due(
        self,
        business_id: str,
        case_id: str,
        expected_decision: ContextualFollowUpDecision,
        now: datetime,
        message_text: str,
        delivered: bool,
        twilio_sid: str | None,
    ) -> str:
        with self.unit_of_work_factory() as uow:
            prepared = self._prepare(uow, business_id, case_id, now)
            if prepared is None:
                return "gone"
            decision, _snapshot, _text, _dna, profile = prepared
            if (
                not decision.due
                or decision.follow_up_reason != expected_decision.follow_up_reason
                or decision.attempt_number != expected_decision.attempt_number
            ):
                return "not_due"
            case = uow.cases.get(business_id, case_id)
            if case is None:
                return "gone"
            expected_version = case.version
            existing_event_count = len(case.event_history)
            case.record(ProcessEvent(
                EventType.SALES_FOLLOW_UP_SENT,
                occurred_at=now,
                source="sales_contextual_follow_up",
                payload={
                    "reason": decision.follow_up_reason.value if decision.follow_up_reason else None,
                    "move": SalesMove.SEND_CONTEXTUAL_FOLLOW_UP.value,
                    "attempt_number": decision.attempt_number,
                    "message_fingerprint": hashlib.sha256(
                        message_text.encode("utf-8")
                    ).hexdigest(),
                    "delivered": delivered,
                    "twilio_sid": twilio_sid,
                },
            ))
            try:
                uow.cases.save(case, expected_version)
            except StaleCaseError:
                return "stale"
            uow.events.add_many(
                business_id, case.case_id, case.event_history[existing_event_count:]
            )
            try:
                self._record_profile_attempt(uow, profile, decision, now)
            except StaleSalesProfileError:
                return "stale"
            _mirror_into_conversations(
                uow,
                business_id,
                case.case_id,
                message_text=message_text,
                attempt_number=decision.attempt_number or 1,
                reason=decision.follow_up_reason,
                delivered=delivered,
                now=now,
            )
            uow.commit()
            _log_event(
                logging.INFO,
                "sales_contextual_follow_up_sent",
                business_id=business_id,
                case_id=case_id,
                reason=None if decision.follow_up_reason is None else decision.follow_up_reason.value,
                attempt_number=decision.attempt_number,
                delivered=delivered,
            )
            return "sent"

    def _prepare(
        self,
        uow: Any,
        business_id: str,
        case_id: str,
        now: datetime,
        *,
        for_update: bool = False,
    ) -> tuple[
        ContextualFollowUpDecision,
        ContextualFollowUpSnapshot,
        str,
        Mapping[str, Any],
        CustomerSalesProfile,
    ] | None:
        case = uow.cases.get(business_id, case_id, for_update=for_update)
        if case is None:
            return None
        dna_version = uow.business_dna.get_active(business_id)
        if dna_version is None:
            return None
        dna = dna_version.configuration
        profile = uow.sales_profiles.get(business_id, case_id, for_update=for_update)
        if profile is None:
            profile = CustomerSalesProfile(business_id, case_id)
        conversations = uow.conversations.list_for_case(business_id, case_id)
        human_owns = any(item.status in _HUMAN_OWNED for item in conversations)
        playbook = uow.sales_playbooks.get_active(business_id)
        playbook_config = None if playbook is None else dict(playbook.configuration)
        cadence, maximum_attempts, quiet_hours = cadence_from_config(playbook_config, dna)
        customer_timezone = next(
            (
                item.metadata.get("customer_timezone")
                for item in conversations
                if isinstance(item.metadata.get("customer_timezone"), str)
            ),
            None,
        )
        snapshot = ContextualFollowUpSnapshot(
            process_state=case.current_state,
            sales_stage=profile.stage,
            callback_requested=_callback_requested(case, profile),
            objection_deferred=_objection_deferred(profile),
            preferred_contact_at=profile.preferred_contact_at,
            last_inbound_at=_last_inbound_at(uow, conversations),
            last_sales_follow_up_at=_last_sales_follow_up_at(case),
            attempts_sent=_attempts_sent(profile),
            sms_consent=bool(case.lead.sms_consent),
            has_phone=bool(case.lead.phone),
            sms_suppressed=bool(
                case.lead.phone and self.sms_service.is_suppressed(business_id, case.lead.phone)
            ),
            human_owns=human_owns,
            timezone_name=timezone_from_sources(customer_timezone, dna),
            quiet_hours=quiet_hours,
            cadence_hours=cadence,
            maximum_attempts=maximum_attempts,
        )
        decision = decide_contextual_follow_up(snapshot, now)
        fallback = phrase_contextual_follow_up(
            decision.follow_up_reason or FollowUpReason.OBJECTION_DEFERRED
        )
        message_text = fallback
        if decision.due and decision.sendable and decision.follow_up_reason is not None:
            message_text = self._phrase(
                decision.follow_up_reason, fallback, dna, profile,
            )
        return decision, snapshot, message_text, dna, profile

    def _phrase(
        self,
        reason: FollowUpReason,
        fallback: str,
        dna: Mapping[str, Any],
        profile: CustomerSalesProfile,
    ) -> str:
        candidate = SalesResponseCandidate(
            message_text=fallback,
            move=SalesMove.SEND_CONTEXTUAL_FOLLOW_UP,
            used_safe_fallback=self._generator is None,
        )
        if self._generator is not None:
            try:
                from src.ai.sales_response_adapter import to_sales_response_candidate
                from src.ai.sales_response_generator import SalesResponseGenerationInput

                generated = self._generator.generate(SalesResponseGenerationInput(
                    approved_move=SalesMove.SEND_CONTEXTUAL_FOLLOW_UP,
                    sales_stage=profile.stage if profile.stage is not SalesStage.GREETING else SalesStage.FOLLOW_UP,
                    channel="sms",
                    customer_tone="neutral",
                    knowledge_cards=[],
                    business_facts=[
                        {"business_fact_id": fact_id, "text": text}
                        for fact_id, text in listed_business_facts(dna, None)
                    ],
                    customer_evidence=[],
                    handoff_template=None,
                    safe_fallback_text=fallback,
                    conversation_context={
                        "follow_up_reason": reason.value,
                        "approved_move": SalesMove.SEND_CONTEXTUAL_FOLLOW_UP.value,
                    },
                    customer_message="",
                ))
                candidate = to_sales_response_candidate(generated.output)
            except (AIProviderError, AIInvalidOutputError, AttributeError):
                candidate = SalesResponseCandidate(
                    message_text=fallback,
                    move=SalesMove.SEND_CONTEXTUAL_FOLLOW_UP,
                    used_safe_fallback=True,
                )
        fact_map = dict(listed_business_facts(dna, None))
        result = self._validator.validate(
            candidate,
            SalesResponseValidationContext(
                approved_move=SalesMove.SEND_CONTEXTUAL_FOLLOW_UP,
                approved_knowledge=frozenset(),
                approved_business_facts=fact_map,
                customer_evidence={},
                safe_fallback=fallback,
            ),
        )
        return result.message_text or fallback

    @staticmethod
    def _record_profile_attempt(
        uow: Any,
        profile: CustomerSalesProfile,
        decision: ContextualFollowUpDecision,
        now: datetime,
    ) -> None:
        current = uow.sales_profiles.get(profile.business_id, profile.case_id, for_update=True)
        if current is None:
            current = profile
            exists = False
        else:
            exists = True
        metadata = dict(current.metadata)
        follow = dict(metadata.get("sales_follow_up") or {})
        follow["attempts_sent"] = decision.attempt_number
        follow["last_reason"] = (
            None if decision.follow_up_reason is None else decision.follow_up_reason.value
        )
        follow["last_sent_at"] = now.isoformat()
        metadata["sales_follow_up"] = follow
        stage = current.stage
        if stage is SalesStage.NURTURE:
            stage = SalesStage.FOLLOW_UP
        persisted = replace(
            current,
            stage=stage,
            last_move=SalesMove.SEND_CONTEXTUAL_FOLLOW_UP,
            metadata=metadata,
        )
        if not exists:
            uow.sales_profiles.add(persisted, now=now)
        else:
            uow.sales_profiles.save(persisted, current.version, now=now)


def _callback_requested(case: Any, profile: CustomerSalesProfile) -> bool:
    if profile.metadata.get("callback_status") == "requested":
        return True
    if profile.last_move is SalesMove.SCHEDULE_CALLBACK:
        return True
    return any(
        event.event_type == EventType.CALLBACK_REQUESTED
        for event in case.event_history
    )


def _objection_deferred(profile: CustomerSalesProfile) -> bool:
    return (
        profile.active_objection is not None
        and profile.active_objection.status is ObjectionStatus.DEFERRED
    )


def _attempts_sent(profile: CustomerSalesProfile) -> int:
    raw = profile.metadata.get("sales_follow_up")
    if not isinstance(raw, Mapping):
        return 0
    value = raw.get("attempts_sent", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _last_sales_follow_up_at(case: Any) -> datetime | None:
    timestamps = [
        event.occurred_at
        for event in case.event_history
        if event.event_type == EventType.SALES_FOLLOW_UP_SENT
    ]
    return max(timestamps) if timestamps else None


def _last_inbound_at(uow: Any, conversations: tuple[Any, ...]) -> datetime | None:
    latest: datetime | None = None
    for conversation in conversations:
        messages = uow.conversation_messages.list_for_conversation(
            conversation.business_id, conversation.conversation_id, limit=50,
        )
        for message in messages:
            if message.direction is not MessageDirection.INBOUND:
                continue
            if latest is None or message.created_at > latest:
                latest = message.created_at
    return latest


def _mirror_into_conversations(
    uow: Any,
    business_id: str,
    case_id: str,
    *,
    message_text: str,
    attempt_number: int,
    reason: FollowUpReason | None,
    delivered: bool,
    now: datetime,
) -> None:
    fingerprint = hashlib.sha256(message_text.encode("utf-8")).hexdigest()
    external_id = f"sales-followup:{attempt_number}"
    for conversation in uow.conversations.list_for_case(business_id, case_id):
        if conversation.status is ConversationStatus.CLOSED:
            continue
        if uow.conversation_messages.get_by_external_id(
            business_id, conversation.conversation_id, external_id
        ):
            continue
        try:
            sequence = uow.conversation_messages.next_sequence(
                business_id, conversation.conversation_id
            )
            uow.conversation_messages.add(
                ConversationMessage(
                    message_id=str(uuid4()),
                    business_id=business_id,
                    conversation_id=conversation.conversation_id,
                    sequence_number=sequence,
                    direction=MessageDirection.OUTBOUND,
                    role=MessageRole.ASSISTANT,
                    text=message_text,
                    created_at=now,
                    external_message_id=external_id,
                    content_fingerprint=fingerprint,
                    metadata={
                        "sales_follow_up": True,
                        "reason": None if reason is None else reason.value,
                        "delivered": delivered,
                    },
                )
            )
            expected_version = conversation.version
            conversation.touch(now)
            uow.conversations.save(conversation, expected_version)
        except StaleCaseError:
            LOGGER.warning(
                "sales_follow_up_conversation_stale business_id=%s conversation_id=%s",
                business_id,
                conversation.conversation_id,
            )


def _log_event(level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **{key: value for key, value in fields.items() if value is not None}}
    LOGGER.log(level, json.dumps(payload, separators=(",", ":"), default=str))
