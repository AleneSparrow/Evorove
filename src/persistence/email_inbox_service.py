"""Replies to cycle-2 cold email continue the sales dialogue (roadmap step 16).

Each business's own mailbox is read over IMAP (the same mailbox it sends
from, step 13), so no provider webhook is needed. Only replies from people
cycle 2 actually wrote to are taken; everything else in the inbox is left
alone. A reply that opts out ("no", "unsubscribe", "remove me"...) is
honored like the unsubscribe link (step 15). Any other reply goes through
the same sales-led intake as SMS: SalesPolicyEngine picks the next move, the
answer is emailed back in the same thread, and the CRM card shows both
messages right away.
"""

from __future__ import annotations

import hashlib
import imaplib
import logging
import re
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from email import message_from_bytes, policy
from email.utils import parseaddr
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from src.domain.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    MessageDirection,
    MessageRole,
)
from src.domain.models import utc_now
from src.domain.qualification import IncomingMessage

from .crm_board_service import CrmBoardService
from .email_outreach_service import EmailOutreachService
from .outreach_service import OutreachService
from .sqlalchemy_models import EmailConnectionRow, OutreachProspectRow

if TYPE_CHECKING:
    from .lead_intake import PersistentLeadIntakeService
    from .repositories import UnitOfWorkFactory

LOGGER = logging.getLogger("uvicorn.error")

EMAIL_CHANNEL = "email"
_IMAP_TIMEOUT_SECONDS = 20
_MAX_PER_POLL = 50
_TEXT_LIMIT = 4000
_HUMAN_STATUSES = frozenset({ConversationStatus.HUMAN_TAKEOVER_REQUESTED, ConversationStatus.HUMAN_TAKEOVER_ACTIVE, ConversationStatus.CLOSED})
_TOKEN_TTL = timedelta(days=3650)  # the email thread has no browser token
_QUOTE_START = re.compile(
    r"^(>|On .+wrote:\s*$|-{2,}\s*Original Message|From:\s|Sent from my )", re.IGNORECASE
)
_OPT_OUT_LINE = frozenset({
    "no", "no thanks", "no thank you", "nope", "stop", "unsubscribe", "remove", "remove me",
    "please remove me", "not interested", "no interest",
})
_OPT_OUT_ANYWHERE = re.compile(
    r"\b(unsubscribe|remove me|take me off|stop (emailing|contacting|writing|sending)|"
    r"do not (email|contact)|don'?t (email|contact)|not interested)\b",
    re.IGNORECASE,
)
_AUTO_SUBJECT = re.compile(r"^(automatic reply|auto(matic)?[- ]?reply|out of (the )?office|auto:)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ImapTarget:
    host: str
    port: int
    username: str
    password: str


@dataclass(frozen=True, slots=True)
class InboundEmail:
    uid: int
    message_id: str
    from_address: str
    subject: str
    text: str
    in_reply_to: str | None = None
    references: str | None = None
    automatic: bool = False


Fetcher = Callable[[ImapTarget, int | None], tuple[list[InboundEmail], int | None]]


def imap_fetch(target: ImapTarget, last_uid: int | None) -> tuple[list[InboundEmail], int | None]:
    """New INBOX messages after `last_uid`, read-only. The first read only
    records where the inbox is now, so old mail is never treated as a reply."""
    client = imaplib.IMAP4_SSL(
        target.host, target.port, ssl_context=ssl.create_default_context(), timeout=_IMAP_TIMEOUT_SECONDS
    )
    try:
        client.login(target.username, target.password)
        client.select("INBOX", readonly=True)
        _, data = client.uid("SEARCH", None, "ALL" if last_uid is None else f"UID {last_uid + 1}:*")
        uids = sorted(int(uid) for uid in (data[0] or b"").split())
        if last_uid is None:
            return [], (uids[-1] if uids else 0)
        messages: list[InboundEmail] = []
        for uid in [uid for uid in uids if uid > last_uid][:_MAX_PER_POLL]:
            _, parts = client.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = next((part[1] for part in parts if isinstance(part, tuple)), None)
            if raw is not None:
                messages.append(parse_email(uid, raw))
        return messages, (messages[-1].uid if messages else last_uid)
    finally:
        try:
            client.logout()
        except Exception:  # noqa: BLE001
            pass


def parse_email(uid: int, raw: bytes) -> InboundEmail:
    message = message_from_bytes(raw, policy=policy.default)
    body = message.get_body(preferencelist=("plain",))
    text = body.get_content() if body is not None else ""
    subject = str(message.get("Subject") or "")
    auto_submitted = str(message.get("Auto-Submitted") or "no").strip().casefold()
    precedence = str(message.get("Precedence") or "").strip().casefold()
    automatic = (
        auto_submitted != "no"
        or precedence in {"bulk", "junk", "auto_reply", "list"}
        or message.get("X-Autoreply") is not None
        or message.get("X-Autorespond") is not None
        or bool(_AUTO_SUBJECT.match(subject.strip()))
    )
    return InboundEmail(
        uid=uid,
        message_id=str(message.get("Message-ID") or f"<uid-{uid}-{uuid4()}@unknown>").strip(),
        from_address=parseaddr(str(message.get("From") or ""))[1].strip().casefold(),
        subject=subject,
        text=text,
        in_reply_to=(str(message.get("In-Reply-To")).strip() if message.get("In-Reply-To") else None),
        references=(str(message.get("References")).strip() if message.get("References") else None),
        automatic=automatic,
    )


def reply_text(text: str) -> str:
    """The new part of a reply, without the quoted thread below it."""
    kept: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if _QUOTE_START.match(line.strip()):
            break
        kept.append(line)
    return "\n".join(kept).strip()[:_TEXT_LIMIT]


def is_opt_out(text: str) -> bool:
    first_line = next((line for line in text.split("\n") if line.strip()), "")
    normalized = re.sub(r"[^a-z' ]", "", first_line.casefold()).strip()
    return normalized in _OPT_OUT_LINE or bool(_OPT_OUT_ANYWHERE.search(text[:500]))


class EmailInboxService:
    def __init__(
        self,
        unit_of_work_factory: "UnitOfWorkFactory",
        *,
        email: EmailOutreachService,
        outreach: OutreachService,
        board: CrmBoardService,
        intake: "PersistentLeadIntakeService",
        fetcher: Fetcher | None = None,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self._email = email
        self._outreach = outreach
        self._board = board
        self._intake = intake
        self._fetcher = fetcher or imap_fetch

    def poll_all(self) -> dict[str, int]:
        totals = {"received": 0, "replied": 0, "opted_out": 0}
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return totals
            business_ids = list(
                session.scalars(select(EmailConnectionRow.business_id).where(EmailConnectionRow.imap_host.is_not(None))).all()
            )
        for business_id in business_ids:
            try:
                for key, value in self.poll(business_id).items():
                    totals[key] += value
            except Exception:  # noqa: BLE001 -- one mailbox never stops the others
                LOGGER.exception("email_inbox_poll_failed business_id=%s", business_id)
        return totals

    def poll(self, business_id: str) -> dict[str, int]:
        counts = {"received": 0, "replied": 0, "opted_out": 0}
        with self.unit_of_work_factory() as uow:
            mailbox = uow.session.get(EmailConnectionRow, business_id)
            if mailbox is None or not mailbox.imap_host:
                return counts
            target = ImapTarget(
                mailbox.imap_host,
                mailbox.imap_port or 993,
                mailbox.smtp_username,
                self._email._box().decrypt(mailbox.password_encrypted),
            )
            last_uid, own_address = mailbox.imap_last_uid, mailbox.from_address.casefold()
        messages, newest = self._fetcher(target, last_uid)
        cursor = last_uid if messages else newest
        for message in messages:
            try:
                outcome = self._handle(business_id, own_address, message)
            except Exception:  # noqa: BLE001 -- retried on the next sweep; intake is idempotent
                LOGGER.exception("email_reply_failed business_id=%s uid=%s", business_id, message.uid)
                break
            cursor = message.uid
            if outcome:
                counts["received"] += 1
                counts[outcome] = counts.get(outcome, 0) + 1
        with self.unit_of_work_factory() as uow:
            mailbox = uow.session.get(EmailConnectionRow, business_id)
            if mailbox is not None and cursor is not None and cursor != mailbox.imap_last_uid:
                mailbox.imap_last_uid = cursor
                uow.commit()
        return counts

    def _handle(self, business_id: str, own_address: str, message: InboundEmail) -> str | None:
        sender = message.from_address
        if not sender or sender == own_address or message.automatic:
            return None
        with self.unit_of_work_factory() as uow:
            prospect = next(
                (
                    row
                    for row in uow.session.scalars(
                        select(OutreachProspectRow).where(
                            OutreachProspectRow.business_id == business_id,
                            OutreachProspectRow.status.in_(("sent", "stopped")),
                        )
                    ).all()
                    if (row.email or "").casefold() == sender
                ),
                None,
            )
            if prospect is None:
                return None  # not someone cycle 2 wrote to: leave the inbox alone
            person = {
                "person_id": prospect.person_id,
                "name": prospect.name,
                "status": prospect.status,
                "subject": prospect.subject or "",
                "body": prospect.body or "",
            }
        text = reply_text(message.text)
        if not text:
            return None
        if is_opt_out(text):
            self._outreach.unsubscribe(business_id, sender, reason="reply_opt_out")
            return "opted_out"
        if (
            person["status"] == "stopped"
            or self._email.is_suppressed(business_id, email=sender)
            or self._taken_over(business_id, sender)
        ):
            self._board.report_touch(
                business_id,
                touch_id=f"evorove:email-in:{_digest(message.message_id)}",
                kind="message",
                summary=f"Customer: {text}",
                identity={"email": sender, "name": person["name"] or ""},
                person_id=person["person_id"],
                payload={"direction": "inbound", "channel": EMAIL_CHANNEL},
            )
            return None  # outreach stopped by the owner: shown on the card, not answered
        self._seed_conversation(business_id, sender, person)
        result = self._intake.receive(
            IncomingMessage(
                business_id=business_id,
                channel=EMAIL_CHANNEL,
                external_message_id=message.message_id[:255],
                raw_text=text,
                timestamp=utc_now(),
                customer_name=person["name"],
                email=sender,
            ),
            sales_led_conversation=True,
        )
        if result.response is not None and not result.duplicate:
            self._send_reply(business_id, sender, message, result.response.message_text, person["person_id"])
        self._board.report_case(business_id, result.case_id)
        return "replied"

    def _taken_over(self, business_id: str, sender: str) -> bool:
        with self.unit_of_work_factory() as uow:
            conversation = uow.conversations.get_by_channel_session(business_id, EMAIL_CHANNEL, sender)
            return conversation is not None and conversation.status in _HUMAN_STATUSES

    def _seed_conversation(self, business_id: str, sender: str, person: dict[str, Any]) -> None:
        """Put the first cold email into the email conversation once, so the
        sales engine answers knowing what was written."""
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            uow.conversations.lock_session_identity(business_id, EMAIL_CHANNEL, sender)
            if uow.conversations.get_by_channel_session(business_id, EMAIL_CHANNEL, sender, for_update=True):
                return
            conversation = Conversation(
                conversation_id=str(uuid4()),
                business_id=business_id,
                token_hash=hashlib.sha256(f"{EMAIL_CHANNEL}-unusable:{business_id}:{sender}".encode()).hexdigest(),
                channel=EMAIL_CHANNEL,
                status=ConversationStatus.AI_ACTIVE,
                created_at=now,
                updated_at=now,
                last_activity_at=now,
                token_expires_at=now + _TOKEN_TTL,
                token_revoked_at=now,
                external_session_id=sender,
            )
            uow.conversations.add(conversation)
            uow.session.flush()
            text = f"{person['subject']}\n\n{person['body']}".strip()
            uow.conversation_messages.add(
                ConversationMessage(
                    message_id=str(uuid4()),
                    business_id=business_id,
                    conversation_id=conversation.conversation_id,
                    sequence_number=uow.conversation_messages.next_sequence(business_id, conversation.conversation_id),
                    direction=MessageDirection.OUTBOUND,
                    role=MessageRole.ASSISTANT,
                    text=text,
                    created_at=now,
                    external_message_id=f"cold:{person['person_id']}",
                    content_fingerprint=hashlib.sha256(text.encode()).hexdigest(),
                )
            )
            uow.commit()

    def _send_reply(self, business_id: str, sender: str, message: InboundEmail, answer: str, person_id: str) -> None:
        with self.unit_of_work_factory() as uow:
            mailbox = uow.session.get(EmailConnectionRow, business_id)
            footer = f"\n\n{mailbox.from_name}\n\n--\n{mailbox.postal_address}" if mailbox else ""
        subject = message.subject.strip() or "Your reply"
        if not subject.casefold().startswith("re:"):
            subject = f"Re: {subject}"
        references = " ".join(part for part in (message.references, message.message_id) if part)
        outbox_id = f"email-reply:{business_id}:{_digest(message.message_id)}"
        self._email.enqueue(
            business_id,
            to_address=sender,
            subject=subject[:255],
            body=f"{answer.strip()}{footer}",
            headers={"In-Reply-To": message.message_id, "References": references[-900:]},
            meta={"person_id": person_id, "in_reply_to": message.message_id},
            outbox_id=outbox_id,
        )
        self._email.deliver_one(outbox_id)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]
