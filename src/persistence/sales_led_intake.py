"""Sales-led intake for SMS and staff REST /messages.

Qualification stays an operational side check. Completeness does not advance
ProcessState to QUALIFIED. The customer-facing reply comes from
SalesPolicyEngine, matching live web chat. QUALIFIED opens only after
commitment and an explicit ready signal.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Mapping
from uuid import uuid4

from src.domain.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    MessageDirection,
    MessageRole,
)
from src.domain.models import ProcessCase
from src.domain.qualification import (
    CustomerResponse,
    IncomingMessage,
    LeadIntakeResult,
    QualificationReasonCode,
    QualificationResult,
)
from src.domain.states import ProcessState
from src.engine.lead_intake import LeadIntakeService
from src.persistence.commercial_service import CommercialWorkflowService
from src.persistence.lead_intake import PersistentLeadIntakeService
from src.persistence.repositories import ClaimStatus, UnitOfWork
from src.persistence.sales_live_turn import SalesLiveTurnService
from src.persistence.sms_thread_service import SMS_CHANNEL


_COMMERCIAL_STATES = frozenset({
    ProcessState.QUALIFIED,
    ProcessState.QUOTED,
    ProcessState.BOOKED,
    ProcessState.WON,
})
_CONTEXT_MESSAGE_LIMIT = 8
_TOKEN_TTL = timedelta(days=3650)


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SalesLedIntakeService:
    """Drive one inbound customer message on a non-widget channel."""

    def __init__(self, intake: PersistentLeadIntakeService) -> None:
        self.intake = intake
        self.commercial = CommercialWorkflowService()
        self.sales_live = SalesLiveTurnService(
            analyzer=intake.sales_turn_analyzer,  # type: ignore[arg-type]
            response_generator=intake.sales_response_generator,  # type: ignore[arg-type]
            commercial=self.commercial,
            process_engine=intake.process_engine,
        )

    def receive(self, message: IncomingMessage) -> LeadIntakeResult:
        with self.intake.unit_of_work_factory() as uow:
            result = self._receive_in_unit_of_work(uow, message)
            uow.commit()
            return result

    def _receive_in_unit_of_work(
        self,
        uow: UnitOfWork,
        message: IncomingMessage,
    ) -> LeadIntakeResult:
        occurred_at = message.timestamp
        session_id = self._session_id(message)
        conversation = self._lock_existing_conversation(uow, message, session_id)
        if conversation is not None and conversation.case_id is not None:
            case = uow.cases.get(message.business_id, conversation.case_id)
            if case is not None and case.current_state in _COMMERCIAL_STATES:
                return self._continue_commercial(
                    uow, message, conversation, case, occurred_at,
                )

        result = self.intake.receive_in_unit_of_work(
            uow,
            message,
            sales_led_conversation=True,
            complete_idempotency=False,
        )
        if result.duplicate:
            return result

        conversation = self._ensure_conversation(
            uow, message, result.lead_id, conversation, session_id, occurred_at,
        )
        expected_version = conversation.version
        prior = uow.conversation_messages.list_for_conversation(
            conversation.business_id,
            conversation.conversation_id,
            limit=_CONTEXT_MESSAGE_LIMIT,
        )
        inbound = self._record_inbound(
            uow, conversation, message, occurred_at,
        )
        conversation.link_case(result.lead_id, result.case_id)
        dna = self._active_dna(uow, message.business_id)

        if result.current_state in {ProcessState.LOST, ProcessState.NEEDS_HUMAN}:
            response = result.response
            process_state = result.current_state
            requires_human = result.current_state is ProcessState.NEEDS_HUMAN
        else:
            case = uow.cases.get(message.business_id, result.case_id)
            if case is None:
                raise RuntimeError("sales-led intake references a missing case")
            live = self.sales_live.run(
                uow,
                conversation,
                case,
                dna,
                result.qualification,
                source_message_id=inbound.message_id,
                customer_text=message.raw_text,
                prior_messages=prior,
                occurred_at=occurred_at,
            )
            response = CustomerResponse(
                message_text=live.message_text,
                channel=message.channel,
                reason=live.reason,
                related_case_id=result.case_id,
                requires_human=live.requires_human,
            )
            process_state = live.process_state
            requires_human = live.requires_human
            result = replace(result, current_state=process_state, response=response)

        if response is not None:
            self._record_outbound(
                uow, conversation, message, response.message_text, occurred_at,
            )
        conversation.metadata["current_state"] = process_state.value
        if requires_human or process_state is ProcessState.NEEDS_HUMAN:
            conversation.set_status(
                ConversationStatus.HUMAN_TAKEOVER_REQUESTED, occurred_at,
            )
        conversation.touch(occurred_at)
        uow.conversations.save(conversation, expected_version)
        uow.idempotency.complete(
            message.business_id,
            message.channel.casefold(),
            message.external_message_id,
            result.case_id,
            PersistentLeadIntakeService._serialize_result(result),
        )
        return result

    def _continue_commercial(
        self,
        uow: UnitOfWork,
        message: IncomingMessage,
        conversation: Conversation,
        case: ProcessCase,
        occurred_at: datetime,
    ) -> LeadIntakeResult:
        fingerprint = PersistentLeadIntakeService.fingerprint(message)
        channel = message.channel.casefold()
        claim_status, claim = uow.idempotency.claim(
            message.business_id, channel, message.external_message_id, fingerprint,
        )
        if claim_status is ClaimStatus.COMPLETED:
            if claim.result is None or claim.case_id is None:
                raise RuntimeError("completed commercial message has no persisted result")
            return PersistentLeadIntakeService._deserialize_result(
                claim.result, duplicate=True,
            )

        dna = self._active_dna(uow, message.business_id)
        expected_version = conversation.version
        self._record_inbound(uow, conversation, message, occurred_at)
        commercial = self.commercial.handle_message(
            uow,
            case,
            dna,
            conversation.metadata,
            message.raw_text,
            occurred_at=occurred_at,
        )
        response = CustomerResponse(
            message_text=commercial.message_text,
            channel=message.channel,
            reason=commercial.reason,
            related_case_id=case.case_id,
            requires_human=commercial.requires_human,
        )
        process_state = ProcessState(commercial.current_state)
        qualification = _commercial_qualification(case)
        result = LeadIntakeResult(
            case.case_id,
            case.lead.lead_id,
            process_state,
            qualification,
            response,
            False,
        )
        self._record_outbound(
            uow, conversation, message, response.message_text, occurred_at,
        )
        conversation.metadata["current_state"] = process_state.value
        conversation.metadata["unresolved_items"] = []
        if commercial.requires_human or process_state is ProcessState.NEEDS_HUMAN:
            conversation.set_status(
                ConversationStatus.HUMAN_TAKEOVER_REQUESTED, occurred_at,
            )
        conversation.touch(occurred_at)
        uow.conversations.save(conversation, expected_version)
        uow.idempotency.complete(
            message.business_id,
            channel,
            message.external_message_id,
            case.case_id,
            PersistentLeadIntakeService._serialize_result(result),
        )
        return result

    def _lock_existing_conversation(
        self,
        uow: UnitOfWork,
        message: IncomingMessage,
        session_id: str | None,
    ) -> Conversation | None:
        if not session_id:
            return None
        uow.conversations.lock_session_identity(
            message.business_id, message.channel.casefold(), session_id,
        )
        return uow.conversations.get_by_channel_session(
            message.business_id,
            message.channel.casefold(),
            session_id,
            for_update=True,
        )

    def _ensure_conversation(
        self,
        uow: UnitOfWork,
        message: IncomingMessage,
        lead_id: str,
        existing: Conversation | None,
        session_id: str | None,
        occurred_at: datetime,
    ) -> Conversation:
        if existing is not None:
            return existing
        identity = session_id or f"lead:{lead_id}"
        channel = message.channel.casefold()
        uow.conversations.lock_session_identity(
            message.business_id, channel, identity,
        )
        conversation = uow.conversations.get_by_channel_session(
            message.business_id, channel, identity, for_update=True,
        )
        if conversation is not None:
            return conversation
        conversation = Conversation(
            conversation_id=str(uuid4()),
            business_id=message.business_id,
            token_hash=_fingerprint(f"{channel}-unusable:{message.business_id}:{identity}"),
            channel=channel,
            status=ConversationStatus.AI_ACTIVE,
            created_at=occurred_at,
            updated_at=occurred_at,
            last_activity_at=occurred_at,
            token_expires_at=occurred_at + _TOKEN_TTL,
            token_revoked_at=occurred_at,
            external_session_id=identity,
        )
        uow.conversations.add(conversation)
        session = getattr(uow, "session", None)
        if session is not None:
            session.flush()
        return conversation

    def _record_inbound(
        self,
        uow: UnitOfWork,
        conversation: Conversation,
        message: IncomingMessage,
        occurred_at: datetime,
    ) -> ConversationMessage:
        existing = uow.conversation_messages.get_by_external_id(
            conversation.business_id,
            conversation.conversation_id,
            message.external_message_id,
        )
        if existing is not None:
            return existing
        sequence = uow.conversation_messages.next_sequence(
            conversation.business_id, conversation.conversation_id,
        )
        inbound = ConversationMessage(
            message_id=str(uuid4()),
            business_id=conversation.business_id,
            conversation_id=conversation.conversation_id,
            sequence_number=sequence,
            direction=MessageDirection.INBOUND,
            role=MessageRole.CUSTOMER,
            text=message.raw_text,
            created_at=occurred_at,
            external_message_id=message.external_message_id,
            content_fingerprint=_fingerprint(message.raw_text),
        )
        uow.conversation_messages.add(inbound)
        return inbound

    def _record_outbound(
        self,
        uow: UnitOfWork,
        conversation: Conversation,
        message: IncomingMessage,
        text: str,
        occurred_at: datetime,
    ) -> None:
        reply_id = f"{message.external_message_id}:reply"
        if uow.conversation_messages.get_by_external_id(
            conversation.business_id, conversation.conversation_id, reply_id,
        ):
            return
        sequence = uow.conversation_messages.next_sequence(
            conversation.business_id, conversation.conversation_id,
        )
        uow.conversation_messages.add(
            ConversationMessage(
                message_id=str(uuid4()),
                business_id=conversation.business_id,
                conversation_id=conversation.conversation_id,
                sequence_number=sequence,
                direction=MessageDirection.OUTBOUND,
                role=MessageRole.ASSISTANT,
                text=text,
                created_at=occurred_at,
                external_message_id=reply_id,
                content_fingerprint=_fingerprint(text),
            )
        )

    @staticmethod
    def _session_id(message: IncomingMessage) -> str | None:
        if message.channel.casefold() == SMS_CHANNEL and message.phone:
            return message.phone
        phone = LeadIntakeService._normalize_phone(message.phone)
        if phone:
            return phone
        return LeadIntakeService._normalize_email(message.email)

    @staticmethod
    def _active_dna(uow: UnitOfWork, business_id: str) -> Mapping[str, Any]:
        version = uow.business_dna.get_active(business_id)
        if version is None:
            raise RuntimeError(f"business has no active Business DNA: {business_id}")
        return PersistentLeadIntakeService._plain_json(version.configuration)


def _commercial_qualification(case: ProcessCase) -> QualificationResult:
    service_id = case.lead.attributes.get("service_requested")
    if not isinstance(service_id, str) or not service_id.strip():
        service_id = None
    return QualificationResult(
        qualified=True,
        reasons=("Commercial workflow is already in progress",),
        reason_codes=(QualificationReasonCode.QUALIFIED,),
        missing_fields=(),
        unanswered_questions=(),
        confidence=1.0,
        recommended_next_state=ProcessState.QUALIFIED,
        requires_human=False,
        booking_allowed=True,
        service_id=service_id,
    )
