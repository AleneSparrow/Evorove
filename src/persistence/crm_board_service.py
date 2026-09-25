"""Report every cycle-2 touch to the Evorove CRM board, durably.

FOUNDATION.md: a step that is not on the board when it happens is not done,
and the owner reads the replies on the card, not only a status word. This
service turns a conversation's committed state into CRM lead-touches
(`dialogue_started`, one `message` per reply, `offer_sent`, `ready_to_book`,
`human_takeover`, `booked`) plus the hot-lead handoff when the sale is ready.

Every touch is an `integration_outbox` row whose id is derived from the
conversation and message, so reporting the same conversation twice enqueues
nothing new, and a crash between commit and HTTP leaves a PENDING row for
POST /api/v1/internal/integrations/deliver. Delivery never raises into the
sales flow. Disabled unless both CRM_BASE_URL and INTERNAL_TASK_SECRET are set.
Customer text only ever goes to the tenant's own CRM board.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from src.domain.models import utc_now

from .sqlalchemy_models import (
    ConversationMessageRow,
    ConversationRow,
    IntegrationOutboxRow,
    OutreachProspectRow,
    LeadRow,
    ProcessCaseRow,
    SalesProfileRow,
)

if TYPE_CHECKING:
    from .repositories import UnitOfWorkFactory

LOGGER = logging.getLogger("uvicorn.error")

TOUCH_KIND = "crm_board_touch"
HOT_LEAD_KIND = "crm_board_hot_lead"
_MAX_ATTEMPTS = 8
_BACKOFF = timedelta(minutes=5)
_SUMMARY_LIMIT = 500

OFFER_SALES_STAGES = frozenset({"PRESENTATION", "COMMITMENT", "BOOKING"})
OFFER_PROCESS_STATES = frozenset({"QUOTED"})
READY_PROCESS_STATES = frozenset({"QUALIFIED"})
BOOKED_PROCESS_STATES = frozenset({"BOOKED"})
HUMAN_STATUSES = frozenset({"human_takeover_requested", "human_takeover_active"})
CHANNELS = {"sms": "sms", "email": "email"}

Poster = Callable[[str, str, dict[str, Any]], tuple[bool, str | None]]


def post_internal_json(url: str, secret: str, payload: dict[str, Any]) -> tuple[bool, str | None]:
    """POST to the operator-configured CRM. Never raises."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "X-Internal-Task-Secret": secret},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return 200 <= response.status < 300, None
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except (urllib.error.URLError, OSError) as exc:
        return False, type(exc).__name__


class CrmBoardService:
    def __init__(
        self,
        unit_of_work_factory: "UnitOfWorkFactory",
        *,
        crm_base_url: str | None,
        secret: str | None,
        poster: Poster | None = None,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self._base_url = (crm_base_url or "").strip().rstrip("/")
        self._secret = secret or ""
        self._poster = poster or post_internal_json

    @property
    def enabled(self) -> bool:
        return bool(self._base_url and self._secret)

    def report_conversation(self, business_id: str, conversation_id: str) -> None:
        """Enqueue every not-yet-reported touch of one conversation, then try to
        deliver them. Call after the turn has committed. Never raises."""
        if not self.enabled:
            return
        try:
            enqueued = self._enqueue(business_id, conversation_id)
            for outbox_id in enqueued:
                self.deliver_one(outbox_id)
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "crm_board_report_error business_id=%s conversation_id=%s",
                business_id,
                conversation_id,
            )

    def report_touch(
        self,
        business_id: str,
        *,
        touch_id: str,
        kind: str,
        summary: str,
        identity: dict[str, str],
        person_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Enqueue and try to deliver one touch that is not a web-chat turn
        (e.g. the first cold email). Idempotent by touch_id. Never raises."""
        if not self.enabled:
            return
        body: dict[str, Any] = {
            "touch_id": touch_id,
            "cycle": 2,
            "kind": kind,
            "source": "evorove",
            "summary": summary[:_SUMMARY_LIMIT],
            "identity": {key: value for key, value in identity.items() if value},
            "payload": dict(payload or {}),
        }
        if person_id:
            body["person_id"] = person_id
        try:
            now = utc_now()
            with self.unit_of_work_factory() as uow:
                session = getattr(uow, "session", None)
                if session is None or session.get(IntegrationOutboxRow, touch_id) is not None:
                    return
                session.add(
                    IntegrationOutboxRow(
                        id=touch_id,
                        business_id=business_id,
                        kind=TOUCH_KIND,
                        payload=body,
                        status="PENDING",
                        attempt_count=0,
                        next_attempt_at=now,
                        last_error=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                uow.commit()
            self.deliver_one(touch_id)
        except Exception:  # noqa: BLE001
            LOGGER.exception("crm_board_touch_error business_id=%s touch_id=%s", business_id, touch_id)

    def report_case(self, business_id: str, case_id: str) -> None:
        """Report every conversation of one case (inbound SMS knows the case,
        not the conversation). Never raises."""
        if not self.enabled:
            return
        try:
            with self.unit_of_work_factory() as uow:
                session = getattr(uow, "session", None)
                if session is None:
                    return
                conversation_ids = list(
                    session.scalars(
                        select(ConversationRow.id).where(
                            ConversationRow.business_id == business_id,
                            ConversationRow.case_id == case_id,
                        )
                    ).all()
                )
        except Exception:  # noqa: BLE001
            LOGGER.exception("crm_board_report_case_error business_id=%s case_id=%s", business_id, case_id)
            return
        for conversation_id in conversation_ids:
            self.report_conversation(business_id, conversation_id)

    def _enqueue(self, business_id: str, conversation_id: str) -> list[str]:
        now = utc_now()
        enqueued: list[str] = []
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return enqueued
            conversation = session.get(ConversationRow, conversation_id)
            if conversation is None or conversation.business_id != business_id:
                return enqueued
            if not conversation.lead_id or not conversation.case_id:
                return enqueued
            lead = session.get(LeadRow, conversation.lead_id)
            case = session.get(ProcessCaseRow, conversation.case_id)
            if lead is None or case is None:
                return enqueued
            if not (lead.email or lead.phone):
                # CRM only accepts addressable people; report once they are.
                return enqueued
            identity = {
                key: value
                for key, value in (("name", lead.name), ("phone", lead.phone), ("email", lead.email))
                if value
            }
            profile = session.get(SalesProfileRow, (business_id, case.id))
            messages = session.scalars(
                select(ConversationMessageRow)
                .where(
                    ConversationMessageRow.business_id == business_id,
                    ConversationMessageRow.conversation_id == conversation_id,
                )
                .order_by(ConversationMessageRow.sequence_number.asc())
            ).all()
            prefix = f"evorove:{conversation_id}"
            # A reply to a cold email belongs to the person cycle 1 found; the
            # first email itself was already put on that card when it was sent.
            prospect = (
                session.scalars(
                    select(OutreachProspectRow).where(
                        OutreachProspectRow.business_id == business_id,
                        func.lower(OutreachProspectRow.email) == lead.email.casefold(),
                    )
                ).first()
                if lead.email
                else None
            )
            messages = [message for message in messages if not (message.external_message_id or "").startswith("cold:")]

            def add(outbox_id: str, kind: str, payload: dict[str, Any]) -> None:
                if session.get(IntegrationOutboxRow, outbox_id) is not None:
                    return
                session.add(
                    IntegrationOutboxRow(
                        id=outbox_id,
                        business_id=business_id,
                        kind=kind,
                        payload=payload,
                        status="PENDING",
                        attempt_count=0,
                        next_attempt_at=now,
                        last_error=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                enqueued.append(outbox_id)

            def touch(key: str, kind: str, summary: str, extra: dict[str, Any] | None = None) -> None:
                touch_id = f"{prefix}:{key}"
                add(
                    touch_id,
                    TOUCH_KIND,
                    {
                        "touch_id": touch_id,
                        "cycle": 2,
                        "kind": kind,
                        "source": "evorove",
                        "summary": summary[:_SUMMARY_LIMIT],
                        "identity": identity,
                        "payload": {"conversation_id": conversation_id, "case_id": case.id, **(extra or {})},
                        **({"person_id": prospect.person_id} if prospect is not None else {}),
                    },
                )

            if messages:
                touch("dialogue", "dialogue_started", f"Conversation started on {conversation.channel}.")
            for message in messages:
                speaker = "Customer" if message.direction == "inbound" else "Evorove"
                touch(
                    f"msg:{message.sequence_number}",
                    "message",
                    f"{speaker}: {message.text}",
                    {"direction": message.direction, "sequence": message.sequence_number},
                )
            stage = profile.stage if profile is not None else None
            if stage in OFFER_SALES_STAGES or case.current_state in OFFER_PROCESS_STATES:
                touch("offer", "offer_sent", "Offer made in the conversation.", {"sales_stage": stage})
            if case.current_state in READY_PROCESS_STATES:
                touch("ready", "ready_to_book", "Ready to book.")
                self._enqueue_hot_lead(add, conversation, case, identity, messages)
            if case.current_state in BOOKED_PROCESS_STATES:
                touch("booked", "booked", "Appointment booked.")
            if conversation.status in HUMAN_STATUSES:
                touch("takeover", "human_takeover", "Handed to a person.")
            uow.commit()
        return enqueued

    @staticmethod
    def _enqueue_hot_lead(add, conversation, case, identity, messages) -> None:  # noqa: ANN001
        service_id = (case.metadata_json or {}).get("service_requested")
        inbound = [message.text for message in messages if message.direction == "inbound"]
        if not service_id or not inbound:
            return
        handoff_id = f"evorove:{case.id}"
        add(
            f"{handoff_id}:hot-lead",
            HOT_LEAD_KIND,
            {
                "handoff_id": handoff_id,
                "source": "evorove",
                "channel": CHANNELS.get(conversation.channel, "web_chat"),
                "identity": identity,
                "service_id": str(service_id),
                "readiness": {"signal": "ready_to_book", "evidence_excerpt": inbound[-1][:4000]},
            },
        )

    def deliver_due(self, *, limit: int = 100) -> dict[str, int]:
        if not self.enabled:
            return {"attempted": 0, "sent": 0, "failed": 0}
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return {"attempted": 0, "sent": 0, "failed": 0}
            ids = list(
                session.scalars(
                    select(IntegrationOutboxRow.id)
                    .where(
                        IntegrationOutboxRow.status == "PENDING",
                        IntegrationOutboxRow.kind.in_((TOUCH_KIND, HOT_LEAD_KIND)),
                        IntegrationOutboxRow.next_attempt_at <= now,
                    )
                    .order_by(IntegrationOutboxRow.created_at.asc(), IntegrationOutboxRow.id.asc())
                    .limit(limit)
                ).all()
            )
        sent = failed = 0
        for outbox_id in ids:
            if self.deliver_one(outbox_id):
                sent += 1
            else:
                failed += 1
        return {"attempted": len(ids), "sent": sent, "failed": failed}

    def deliver_one(self, outbox_id: str) -> bool:
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return False
            row = session.get(IntegrationOutboxRow, outbox_id)
            if row is None or row.status != "PENDING":
                return row is not None and row.status == "SENT"
            route = "lead-touches" if row.kind == TOUCH_KIND else "hot-leads"
            url = f"{self._base_url}/api/v1/internal/businesses/{row.business_id}/{route}"
            delivered, error = self._poster(url, self._secret, dict(row.payload))
            now = utc_now()
            row.attempt_count += 1
            row.updated_at = now
            if delivered:
                row.status = "SENT"
                row.last_error = None
            elif row.attempt_count >= _MAX_ATTEMPTS:
                row.status = "FAILED"
                row.last_error = (error or "delivery_exhausted")[:255]
            else:
                row.next_attempt_at = now + (_BACKOFF * row.attempt_count)
                row.last_error = (error or "delivery_failed")[:255]
            uow.commit()
            return delivered


# Owner commands from the CRM board back to cycle 2 (CRM cycle_command_delivery).
COMMAND_CONVERSATION_STATUS = {
    "pause_outreach": "human_takeover_active",
    "takeover": "human_takeover_active",
    "discard": "closed",
}
# A normal sale stays with the engine; the owner can take over only a
# conversation the engine itself handed off on risk.
_TAKEOVER_FROM = "human_takeover_requested"


def apply_board_command(
    unit_of_work_factory: "UnitOfWorkFactory",
    business_id: str,
    *,
    action: str,
    phone: str | None,
    email: str | None,
    corrected: dict[str, Any] | None = None,
) -> int:
    """Apply one owner command to every conversation of the matching lead(s).

    Stopping automation reuses the human-takeover status the sales flow already
    honours, so a paused or discarded person gets no further automated message.
    Re-applying the same command changes nothing. Returns the number of
    conversations (or, for correct_identity, leads) changed.
    """
    from src.engine.lead_intake import LeadIntakeService

    normalized_phone = LeadIntakeService._normalize_phone(phone) if phone else None
    normalized_email = LeadIntakeService._normalize_email(email) if email else None
    if not normalized_phone and not normalized_email:
        return 0
    now = utc_now()
    changed = 0
    with unit_of_work_factory() as uow:
        session = getattr(uow, "session", None)
        if session is None:
            return 0
        conditions = []
        if normalized_phone:
            conditions.append(LeadRow.normalized_phone == normalized_phone)
        if normalized_email:
            conditions.append(LeadRow.normalized_email == normalized_email)
        leads = session.scalars(
            select(LeadRow).where(LeadRow.business_id == business_id, or_(*conditions))
        ).all()
        if action == "correct_identity":
            changed = _correct_identity(session, business_id, leads, corrected or {}, now)
        elif action in COMMAND_CONVERSATION_STATUS:
            target = COMMAND_CONVERSATION_STATUS[action]
            lead_ids = [lead.id for lead in leads]
            if lead_ids:
                for conversation in session.scalars(
                    select(ConversationRow).where(
                        ConversationRow.business_id == business_id,
                        ConversationRow.lead_id.in_(lead_ids),
                    )
                ).all():
                    if action == "takeover" and conversation.status != _TAKEOVER_FROM:
                        continue
                    if conversation.status != target:
                        conversation.status = target
                        conversation.updated_at = now
                        changed += 1
        uow.commit()
    return changed


def _correct_identity(session, business_id, leads, corrected, now) -> int:  # noqa: ANN001
    from src.engine.lead_intake import LeadIntakeService

    if len(leads) != 1:
        return 0
    lead = leads[0]
    new_phone = corrected.get("phone")
    new_email = corrected.get("email")
    normalized_phone = LeadIntakeService._normalize_phone(new_phone) if new_phone else None
    normalized_email = LeadIntakeService._normalize_email(new_email) if new_email else None
    for column, value in ((LeadRow.normalized_phone, normalized_phone), (LeadRow.normalized_email, normalized_email)):
        if value and session.scalars(
            select(LeadRow.id).where(LeadRow.business_id == business_id, column == value, LeadRow.id != lead.id)
        ).first():
            return 0  # another person already owns this contact; never merge silently
    before = (lead.name, lead.phone, lead.email)
    if corrected.get("name"):
        lead.name = corrected["name"]
    if normalized_phone:
        lead.phone, lead.normalized_phone = new_phone, normalized_phone
    if normalized_email:
        lead.email, lead.normalized_email = new_email, normalized_email
    if (lead.name, lead.phone, lead.email) == before:
        return 0
    lead.updated_at = now
    return 1
