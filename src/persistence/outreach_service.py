"""Cycle 2 writes first to the person on the CRM Cold tab (roadmap step 14).

FOUNDATION.md: the agent itself writes cold to the person from Cold and leads
the conversation. Flow, for every tenant alike (Evorove is client 0):

  CRM `cold_assigned` -> prospect + draft -> owner approves (edits allowed)
  -> cold email from the tenant's own mailbox -> CRM shows it immediately.

The draft is built only from the cycle-1 reason and facts already in the
tenant's Business DNA (name, what it does, service names). It never contains
a price, discount, guarantee or anything else not in the DNA; the owner reads
and approves every message before it goes out. Cold SMS is never sent
(TCPA): a person reachable only by phone is kept and marked skipped.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from sqlalchemy import select

from src.domain.models import utc_now

from .crm_board_service import CrmBoardService
from .email_outreach_service import EmailOutreachError, EmailOutreachService
from .sqlalchemy_models import EmailConnectionRow, IntegrationOutboxRow, OutreachProspectRow

if TYPE_CHECKING:
    from .repositories import UnitOfWorkFactory

_FORBIDDEN = re.compile(r"\$\s?\d|\bdiscount\b|\bguarantee|\bfree trial\b|%\s*off\b", re.IGNORECASE)


class OutreachError(ValueError):
    """Something the owner can fix (no mailbox, wrong state, unsafe edit)."""


@dataclass(frozen=True, slots=True)
class Draft:
    subject: str
    body: str


def draft_first_email(
    dna: Mapping[str, Any] | None,
    *,
    name: str | None,
    reason: str,
    sender_name: str,
    postal_address: str,
) -> Draft:
    """Deterministic first message from the reason and DNA facts only."""
    business = dict((dna or {}).get("business") or {})
    business_name = str(business.get("name") or "our team").strip()
    what_we_do = str(business.get("description") or "").strip().rstrip(".")
    services = [
        str(service.get("name")).strip()
        for service in (dna or {}).get("services") or []
        if isinstance(service, Mapping) and service.get("name")
    ][:3]
    if not what_we_do and services:
        what_we_do = "we help with " + ", ".join(services)
    first_name = (name or "").strip().split(" ")[0] if name and "@" not in name else ""
    greeting = f"Hi {first_name}," if first_name else "Hi there,"
    observed = reason.strip().rstrip(".")
    intro = f"{business_name} — {what_we_do}." if what_we_do else f"I'm with {business_name}."
    body = (
        f"{greeting}\n\n"
        f"I'm reaching out because of this: {observed}.\n\n"
        f"{intro}\n\n"
        "Would it be useful if I sent a short note on how that could work for you?\n\n"
        f"{sender_name}\n{business_name}\n\n"
        f"--\n{postal_address}\n"
        'Not interested? Reply "no" and we will not write again.'
    )
    subject = f"Quick question for {first_name}" if first_name else f"Quick question from {business_name}"
    return Draft(subject=subject[:255], body=body)


def check_message_is_safe(subject: str, body: str) -> None:
    if _FORBIDDEN.search(subject) or _FORBIDDEN.search(body):
        raise OutreachError("the message may not promise a price, discount, guarantee or free offer")


class OutreachService:
    def __init__(
        self,
        unit_of_work_factory: "UnitOfWorkFactory",
        *,
        email: EmailOutreachService,
        board: CrmBoardService,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self._email = email
        self._board = board

    def assign_cold(
        self,
        business_id: str,
        *,
        person_id: str,
        email: str | None,
        phone: str | None,
        name: str | None,
        reason: str,
        reason_source: str,
        hypothesis_id: str | None = None,
    ) -> str:
        """Idempotent: the same person handed over twice keeps its first draft."""
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            session = uow.session
            existing = session.get(OutreachProspectRow, (business_id, person_id))
            if existing is not None:
                return existing.status
            mailbox = session.get(EmailConnectionRow, business_id)
            dna_version = uow.business_dna.get_active(business_id)
            row = OutreachProspectRow(
                business_id=business_id,
                person_id=person_id,
                email=email,
                phone=phone,
                name=name,
                reason=reason or "found by the search for this business",
                reason_source=reason_source or "",
                hypothesis_id=hypothesis_id or None,
                created_at=now,
                updated_at=now,
            )
            if not email:
                row.status, row.skip_reason = "skipped", "no_email_cold_sms_not_allowed"
            elif self._email.is_suppressed(business_id, email=email, phone=phone):
                row.status, row.skip_reason = "skipped", "unsubscribed"
            else:
                draft = draft_first_email(
                    dna_version.configuration if dna_version else None,
                    name=name,
                    reason=row.reason,
                    sender_name=mailbox.from_name if mailbox else "The team",
                    postal_address=mailbox.postal_address if mailbox else "[postal address from the mailbox settings]",
                )
                row.status, row.subject, row.body = "drafted", draft.subject, draft.body
            session.add(row)
            uow.commit()
            return row.status

    def list(self, business_id: str, status: str | None = None) -> list[dict[str, Any]]:
        with self.unit_of_work_factory() as uow:
            query = select(OutreachProspectRow).where(OutreachProspectRow.business_id == business_id)
            if status:
                query = query.where(OutreachProspectRow.status == status)
            rows = uow.session.scalars(query.order_by(OutreachProspectRow.created_at.asc())).all()
            return [_view(row) for row in rows]

    def approve(
        self,
        business_id: str,
        person_id: str,
        *,
        approved_by: str,
        subject: str | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            row = uow.session.get(OutreachProspectRow, (business_id, person_id))
            if row is None:
                raise OutreachError("unknown person")
            if row.status != "drafted":
                raise OutreachError(f"only a drafted message can be approved (now {row.status})")
            if uow.session.get(EmailConnectionRow, business_id) is None:
                raise OutreachError("connect the business mailbox before sending")
            if not self._email.unsubscribe_ready:
                raise OutreachError("the unsubscribe link needs PUBLIC_API_BASE_URL on this deployment")
            if self._email.is_suppressed(business_id, email=row.email, phone=row.phone):
                raise OutreachError("this person unsubscribed")
            final_subject = (subject if subject is not None else row.subject or "").strip()
            final_body = (body if body is not None else row.body or "").strip()
            check_message_is_safe(final_subject, final_body)
            outbox_id = f"cold-email:{business_id}:{person_id}"
            try:
                self._email.enqueue(
                    business_id,
                    to_address=row.email or "",
                    subject=final_subject,
                    body=final_body,
                    meta={"person_id": person_id},
                    outbox_id=outbox_id,
                )
            except EmailOutreachError as exc:
                raise OutreachError(str(exc)) from exc
            row.subject, row.body, row.outbox_id = final_subject, final_body, outbox_id
            row.status, row.approved_by, row.updated_at = "approved", approved_by, now
            uow.commit()
        self._email.deliver_one(outbox_id)
        self.sync_sent(business_id)
        return self.get(business_id, person_id)

    def skip(self, business_id: str, person_id: str) -> dict[str, Any]:
        with self.unit_of_work_factory() as uow:
            row = uow.session.get(OutreachProspectRow, (business_id, person_id))
            if row is None:
                raise OutreachError("unknown person")
            if row.status == "drafted":
                row.status, row.skip_reason, row.updated_at = "skipped", "owner_skipped", utc_now()
                uow.commit()
        return self.get(business_id, person_id)

    def stop(self, business_id: str, *, email: str | None, phone: str | None) -> int:
        """Board command (pause/discard/takeover): nothing more goes out to them."""
        stopped = 0
        with self.unit_of_work_factory() as uow:
            for row in uow.session.scalars(
                select(OutreachProspectRow).where(
                    OutreachProspectRow.business_id == business_id,
                    OutreachProspectRow.status.in_(("drafted", "approved")),
                )
            ).all():
                if (email and (row.email or "").casefold() == email.casefold()) or (phone and row.phone == phone):
                    row.status, row.updated_at = "stopped", utc_now()
                    if row.outbox_id:
                        outbox = uow.session.get(IntegrationOutboxRow, row.outbox_id)
                        if outbox is not None and outbox.status == "PENDING":
                            outbox.status, outbox.last_error = "FAILED", "stopped_by_owner"
                    stopped += 1
            uow.commit()
        return stopped

    def unsubscribe(self, business_id: str, email: str, *, reason: str = "unsubscribe_link") -> bool:
        """The person opted out: suppress, stop anything pending, show it on the CRM card."""
        address = email.strip().casefold()
        new = self._email.suppress(business_id, address, reason=reason)
        self.stop(business_id, email=address, phone=None)
        with self.unit_of_work_factory() as uow:
            prospect = uow.session.scalars(
                select(OutreachProspectRow).where(
                    OutreachProspectRow.business_id == business_id,
                    OutreachProspectRow.email.is_not(None),
                )
            ).all()
            match = next((row for row in prospect if (row.email or "").casefold() == address), None)
            person_id, name = (match.person_id, match.name) if match else (None, None)
        self._board.report_touch(
            business_id,
            touch_id=f"evorove:unsubscribed:{hashlib.sha256(address.encode()).hexdigest()[:24]}",
            kind="stopped",
            summary="Unsubscribed from email. Nothing more will be sent.",
            identity={"email": address, "name": name or ""},
            person_id=person_id,
            payload={"channel": "email", "reason": reason},
        )
        return new

    def get(self, business_id: str, person_id: str) -> dict[str, Any]:
        with self.unit_of_work_factory() as uow:
            row = uow.session.get(OutreachProspectRow, (business_id, person_id))
            if row is None:
                raise OutreachError("unknown person")
            return _view(row)

    def sync_sent(self, business_id: str | None = None) -> int:
        """Mark approved messages whose email actually left as sent and put the
        written message on the CRM card (dialogue_started + message)."""
        reported: list[dict[str, Any]] = []
        with self.unit_of_work_factory() as uow:
            query = select(OutreachProspectRow).where(OutreachProspectRow.status == "approved")
            if business_id:
                query = query.where(OutreachProspectRow.business_id == business_id)
            for row in uow.session.scalars(query).all():
                outbox = uow.session.get(IntegrationOutboxRow, row.outbox_id) if row.outbox_id else None
                if outbox is None or outbox.status != "SENT":
                    continue
                row.status, row.updated_at = "sent", utc_now()
                reported.append(_view(row))
            uow.commit()
        for view in reported:
            identity = {"name": view["name"] or "", "email": view["email"] or "", "phone": view["phone"] or ""}
            prefix = f"evorove:cold:{view['person_id']}"
            self._board.report_touch(
                view["business_id"], touch_id=f"{prefix}:dialogue", kind="dialogue_started",
                summary="First email sent.", identity=identity, person_id=view["person_id"],
                payload={"channel": "email"},
            )
            self._board.report_touch(
                view["business_id"], touch_id=f"{prefix}:msg:1", kind="message",
                summary=f"Evorove: {view['subject']} — {view['body']}", identity=identity,
                person_id=view["person_id"], payload={"direction": "outbound", "channel": "email"},
            )
        return len(reported)


def _view(row: OutreachProspectRow) -> dict[str, Any]:
    return {
        "business_id": row.business_id,
        "person_id": row.person_id,
        "name": row.name,
        "email": row.email,
        "phone": row.phone,
        "reason": row.reason,
        "reason_source": row.reason_source,
        "status": row.status,
        "skip_reason": row.skip_reason,
        "subject": row.subject,
        "body": row.body,
    }
