"""Start a cycle-2 sale on a found person with no inbound customer message."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Mapping, Protocol
from uuid import uuid4

from src.domain.conversations import Conversation, ConversationStatus
from src.domain.found_person import FoundPerson, FoundPersonRejected, parse_found_person
from src.domain.models import Lead, ProcessCase, utc_now
from src.domain.sales import SalesMove
from src.domain.states import ProcessState
from src.persistence.errors import OutboundFirstTouchBlocked
from src.persistence.repositories import ClaimStatus, UnitOfWork, UnitOfWorkFactory
from src.persistence.sales_live_turn import SalesLiveTurnResult, SalesLiveTurnService

_IDEMPOTENCY_CHANNEL = "outbound_first_touch"
_TOKEN_TTL = timedelta(days=3650)


class _OutboundSms(Protocol):
    def is_suppressed(self, business_id: str, phone_number: str) -> bool: ...
    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None: ...


@dataclass(frozen=True, slots=True)
class OutboundFirstTouchResult:
    case_id: str
    conversation_id: str
    lead_id: str
    move: SalesMove
    message_text: str
    delivered: bool
    process_state: ProcessState
    duplicate: bool = False


class OutboundFirstTouchService:
    """Staff/cycle-1 entry: GREET a found person. Consent and STOP are checked here."""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        *,
        sms_service: _OutboundSms | None = None,
        sales_live: SalesLiveTurnService | None = None,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self.sms_service = sms_service
        self.sales_live = sales_live or SalesLiveTurnService()

    def start(
        self,
        business_id: str,
        *,
        idempotency_key: str,
        reason: str,
        source: str,
        channel: str,
        consent_basis: str | None,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        now: datetime | None = None,
    ) -> OutboundFirstTouchResult:
        person = parse_found_person(
            idempotency_key=idempotency_key,
            reason=reason,
            source=source,
            channel=channel,
            consent_basis=consent_basis,
            name=name,
            phone=phone,
            email=email,
        )
        occurred_at = now or utc_now()
        fingerprint = _fingerprint(person)
        external_id = f"outbound:{person.idempotency_key}"
        session_id = f"outbound:{person.source}:{person.address}"
        with self.unit_of_work_factory() as uow:
            self._assert_send_allowed(uow, business_id, person)
            claim_status, claim = uow.idempotency.claim(
                business_id, _IDEMPOTENCY_CHANNEL, external_id, fingerprint,
            )
            if claim_status is ClaimStatus.COMPLETED:
                if claim.result is None:
                    raise RuntimeError("completed outbound first touch has no persisted result")
                return _deserialize(claim.result, duplicate=True)
            uow.conversations.lock_session_identity(
                business_id, person.channel, session_id,
            )
            existing_conversation = uow.conversations.get_by_channel_session(
                business_id, person.channel, session_id, for_update=True,
            )
            if (
                existing_conversation is not None
                and existing_conversation.status is ConversationStatus.AI_ACTIVE
            ):
                raise OutboundFirstTouchBlocked(
                    "conversation_already_active",
                    "A sales conversation is already open for this person on this channel",
                )
            dna = _active_dna(uow, business_id)
            case, conversation = self._open_conversation(
                uow, business_id, person, occurred_at, session_id=session_id,
            )
            live = self.sales_live.start_outbound_greet(
                uow,
                conversation,
                case,
                dna,
                source_message_id=f"{external_id}:greet",
                occurred_at=occurred_at,
                sms_service=self.sms_service,
            )
            if live.move is not SalesMove.GREET_AND_SET_CONTEXT:
                raise RuntimeError("outbound first touch must reuse GREET_AND_SET_CONTEXT")
            result = OutboundFirstTouchResult(
                case_id=case.case_id,
                conversation_id=conversation.conversation_id,
                lead_id=case.lead.lead_id,
                move=live.move,
                message_text=live.message_text,
                delivered=live.delivered,
                process_state=live.process_state,
            )
            uow.idempotency.complete(
                business_id,
                _IDEMPOTENCY_CHANNEL,
                external_id,
                case.case_id,
                _serialize(result),
            )
            uow.commit()
            return result

    def _assert_send_allowed(
        self, uow: UnitOfWork, business_id: str, person: FoundPerson,
    ) -> None:
        if person.channel != "sms":
            return
        phone = person.phone
        if not phone:
            raise OutboundFirstTouchBlocked(
                "found_person_not_addressable",
                "SMS first touch requires a phone number",
            )
        suppressed = False
        if self.sms_service is not None:
            suppressed = self.sms_service.is_suppressed(business_id, phone)
        else:
            session = getattr(uow, "session", None)
            if session is not None:
                from src.persistence.sqlalchemy_models import SmsSuppressionRow

                suppressed = session.get(SmsSuppressionRow, (business_id, phone)) is not None
        if suppressed:
            raise OutboundFirstTouchBlocked(
                "sms_suppressed",
                "STOP is in effect for this number; outbound contact is blocked",
            )

    def _open_conversation(
        self,
        uow: UnitOfWork,
        business_id: str,
        person: FoundPerson,
        occurred_at: datetime,
        session_id: str,
    ) -> tuple[ProcessCase, Conversation]:
        if person.phone:
            uow.leads.lock_identity(business_id, "phone", person.phone)
        if person.email:
            uow.leads.lock_identity(business_id, "email", person.email)
        existing = uow.leads.find_by_identity(business_id, person.phone, person.email)
        sms_consent = person.channel == "sms" and person.consent_basis == "prior_express_written"
        if existing is None:
            lead = Lead(
                lead_id=str(uuid4()),
                name=person.name,
                email=person.email,
                phone=person.phone,
                attributes={
                    "found_reason": person.reason,
                    "found_source": person.source,
                    "outbound_consent_basis": person.consent_basis,
                    "outbound_channel": person.channel,
                },
                sms_consent=sms_consent,
            )
            uow.leads.add(business_id, lead, occurred_at)
        else:
            attributes = dict(existing.attributes)
            attributes.update({
                "found_reason": person.reason,
                "found_source": person.source,
                "outbound_consent_basis": person.consent_basis,
                "outbound_channel": person.channel,
            })
            lead = replace(
                existing,
                name=existing.name or person.name,
                phone=existing.phone or person.phone,
                email=existing.email or person.email,
                attributes=attributes,
                sms_consent=existing.sms_consent or sms_consent,
            )
            uow.leads.save(business_id, lead, occurred_at)
        case = ProcessCase(str(uuid4()), business_id, lead, is_test=False)
        uow.cases.add(case)
        session = getattr(uow, "session", None)
        if session is not None:
            session.flush()
        conversation = Conversation(
            conversation_id=str(uuid4()),
            business_id=business_id,
            token_hash=_fingerprint_text(f"{person.channel}-unusable:{business_id}:{session_id}"),
            channel=person.channel,
            status=ConversationStatus.AI_ACTIVE,
            created_at=occurred_at,
            updated_at=occurred_at,
            last_activity_at=occurred_at,
            token_expires_at=occurred_at + _TOKEN_TTL,
            token_revoked_at=occurred_at,
            external_session_id=session_id,
            metadata={
                "outbound_first_touch": True,
                "found_source": person.source,
            },
        )
        uow.conversations.add(conversation)
        if session is not None:
            session.flush()
        conversation.link_case(lead.lead_id, case.case_id)
        uow.conversations.save(conversation, conversation.version)
        return case, conversation


def _active_dna(uow: UnitOfWork, business_id: str) -> Mapping[str, Any]:
    version = uow.business_dna.get_active(business_id)
    if version is None:
        return {}
    return version.configuration


def _fingerprint(person: FoundPerson) -> str:
    payload = {
        "reason": person.reason,
        "source": person.source,
        "channel": person.channel,
        "consent_basis": person.consent_basis,
        "phone": person.phone,
        "email": person.email,
        "name": person.name,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _fingerprint_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialize(result: OutboundFirstTouchResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "conversation_id": result.conversation_id,
        "lead_id": result.lead_id,
        "move": result.move.value,
        "message_text": result.message_text,
        "delivered": result.delivered,
        "process_state": result.process_state.value,
    }


def _deserialize(payload: Mapping[str, Any], *, duplicate: bool) -> OutboundFirstTouchResult:
    return OutboundFirstTouchResult(
        case_id=str(payload["case_id"]),
        conversation_id=str(payload["conversation_id"]),
        lead_id=str(payload["lead_id"]),
        move=SalesMove(str(payload["move"])),
        message_text=str(payload["message_text"]),
        delivered=bool(payload.get("delivered")),
        process_state=ProcessState(str(payload["process_state"])),
        duplicate=duplicate,
    )
