"""Cycle-2 cold email from each business's own work mailbox (roadmap step 13).

Every tenant connects its own mailbox (any provider with SMTP: Zoho, Google
Workspace, Microsoft 365...). Evorove itself is client 0 and uses the same
path. The password is stored only encrypted with SecretBox and is never
returned. Sending goes through `integration_outbox` (kind `cold_email`) so a
crash never loses or duplicates a message, and a per-mailbox daily cap with a
warm-up ramp protects the sender's reputation: day 1 starts at
WARMUP_START_PER_DAY and grows by WARMUP_STEP_PER_DAY up to the owner's
daily_limit. Quiet hours and message content belong to the callers (steps 14
and 15); this module only connects and delivers.
"""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import func, select

from src.domain.account_security import SecretBox
from src.domain.models import utc_now

from .sqlalchemy_models import EmailConnectionRow, IntegrationOutboxRow

if TYPE_CHECKING:
    from .repositories import UnitOfWorkFactory

LOGGER = logging.getLogger("uvicorn.error")

COLD_EMAIL_KIND = "cold_email"
WARMUP_START_PER_DAY = 10
WARMUP_STEP_PER_DAY = 5
_MAX_ATTEMPTS = 5
_RETRY_BACKOFF = timedelta(minutes=15)
_CAP_BACKOFF = timedelta(hours=1)
_SMTP_TIMEOUT_SECONDS = 15
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class EmailOutreachError(ValueError):
    """A mailbox setting or send request the owner can fix."""


@dataclass(frozen=True, slots=True)
class MailboxSettings:
    from_address: str
    from_name: str
    postal_address: str
    smtp_host: str
    smtp_port: int
    smtp_security: str  # "ssl" (usually 465) or "starttls" (usually 587)
    smtp_username: str
    password: str
    imap_host: str | None = None
    imap_port: int | None = None
    daily_limit: int = 30


@dataclass(frozen=True, slots=True)
class MailboxStatus:
    connected: bool
    from_address: str | None = None
    from_name: str | None = None
    smtp_host: str | None = None
    imap_host: str | None = None
    daily_limit: int | None = None
    todays_cap: int | None = None
    sent_today: int = 0


@dataclass(frozen=True, slots=True)
class SmtpTarget:
    host: str
    port: int
    security: str
    username: str
    password: str


Sender = Callable[[SmtpTarget, EmailMessage], None]


def smtp_send(target: SmtpTarget, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if target.security == "ssl":
        with smtplib.SMTP_SSL(target.host, target.port, timeout=_SMTP_TIMEOUT_SECONDS, context=context) as client:
            client.login(target.username, target.password)
            client.send_message(message)
        return
    with smtplib.SMTP(target.host, target.port, timeout=_SMTP_TIMEOUT_SECONDS) as client:
        client.starttls(context=context)
        client.login(target.username, target.password)
        client.send_message(message)


def todays_cap(daily_limit: int, warmup_started_at: datetime, now: datetime) -> int:
    if warmup_started_at.tzinfo is None:  # SQLite returns naive UTC values
        warmup_started_at = warmup_started_at.replace(tzinfo=timezone.utc)
    days = max(0, (now - warmup_started_at).days)
    return max(1, min(daily_limit, WARMUP_START_PER_DAY + WARMUP_STEP_PER_DAY * days))


class EmailOutreachService:
    def __init__(
        self,
        unit_of_work_factory: "UnitOfWorkFactory",
        *,
        encryption_key: str | None,
        sender: Sender | None = None,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self._encryption_key = encryption_key
        self._sender = sender or smtp_send

    def _box(self) -> SecretBox:
        try:
            return SecretBox(self._encryption_key)
        except ValueError as exc:
            raise EmailOutreachError(
                "Mailbox passwords need ACCOUNT_SECURITY_ENCRYPTION_KEY on this deployment"
            ) from exc

    def connect(self, business_id: str, settings: MailboxSettings) -> MailboxStatus:
        _validate(settings)
        encrypted = self._box().encrypt(settings.password)
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            session = uow.session
            row = session.get(EmailConnectionRow, business_id)
            if row is None:
                row = EmailConnectionRow(business_id=business_id, created_at=now, warmup_started_at=now)
                session.add(row)
            elif row.from_address.casefold() != settings.from_address.casefold():
                row.warmup_started_at = now  # a new sending address starts its warm-up again
            row.from_address = settings.from_address
            row.from_name = settings.from_name
            row.postal_address = settings.postal_address
            row.smtp_host = settings.smtp_host
            row.smtp_port = settings.smtp_port
            row.smtp_security = settings.smtp_security
            row.smtp_username = settings.smtp_username
            row.password_encrypted = encrypted
            row.imap_host = settings.imap_host
            row.imap_port = settings.imap_port
            row.daily_limit = settings.daily_limit
            row.updated_at = now
            uow.commit()
        return self.status(business_id)

    def disconnect(self, business_id: str) -> None:
        with self.unit_of_work_factory() as uow:
            row = uow.session.get(EmailConnectionRow, business_id)
            if row is not None:
                uow.session.delete(row)
                uow.commit()

    def status(self, business_id: str) -> MailboxStatus:
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            row = uow.session.get(EmailConnectionRow, business_id)
            if row is None:
                return MailboxStatus(connected=False)
            return MailboxStatus(
                connected=True,
                from_address=row.from_address,
                from_name=row.from_name,
                smtp_host=row.smtp_host,
                imap_host=row.imap_host,
                daily_limit=row.daily_limit,
                todays_cap=todays_cap(row.daily_limit, row.warmup_started_at, now),
                sent_today=_sent_since(uow.session, business_id, _day_start(now)),
            )

    def enqueue(
        self,
        business_id: str,
        *,
        to_address: str,
        subject: str,
        body: str,
        headers: dict[str, str] | None = None,
        meta: dict[str, Any] | None = None,
        outbox_id: str | None = None,
    ) -> str:
        """Queue one message. `outbox_id` makes the enqueue idempotent."""
        if not to_address or not _EMAIL_RE.fullmatch(to_address.strip()):
            raise EmailOutreachError("recipient email is required")
        if not subject.strip() or not body.strip():
            raise EmailOutreachError("subject and body are required")
        now = utc_now()
        outbox_id = outbox_id or f"cold-email:{uuid4()}"
        with self.unit_of_work_factory() as uow:
            session = uow.session
            if session.get(EmailConnectionRow, business_id) is None:
                raise EmailOutreachError("connect a mailbox before sending")
            if session.get(IntegrationOutboxRow, outbox_id) is None:
                session.add(
                    IntegrationOutboxRow(
                        id=outbox_id,
                        business_id=business_id,
                        kind=COLD_EMAIL_KIND,
                        payload={
                            "to": to_address,
                            "subject": subject,
                            "body": body,
                            "headers": dict(headers or {}),
                            "meta": dict(meta or {}),
                        },
                        status="PENDING",
                        attempt_count=0,
                        next_attempt_at=now,
                        last_error=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                uow.commit()
        return outbox_id

    def deliver_due(self, *, limit: int = 100) -> dict[str, int]:
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
                        IntegrationOutboxRow.kind == COLD_EMAIL_KIND,
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
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            session = uow.session
            row = session.get(IntegrationOutboxRow, outbox_id)
            if row is None or row.status != "PENDING" or row.kind != COLD_EMAIL_KIND:
                return row is not None and row.status == "SENT"
            mailbox = session.get(EmailConnectionRow, row.business_id)
            if mailbox is None:
                row.status, row.last_error, row.updated_at = "FAILED", "mailbox_not_connected", now
                uow.commit()
                return False
            cap = todays_cap(mailbox.daily_limit, mailbox.warmup_started_at, now)
            if _sent_since(session, row.business_id, _day_start(now)) >= cap:
                row.next_attempt_at, row.last_error, row.updated_at = now + _CAP_BACKOFF, "daily_cap", now
                uow.commit()
                return False
            try:
                password = self._box().decrypt(mailbox.password_encrypted)
                message = _build_message(mailbox, row.payload)
                self._sender(
                    SmtpTarget(mailbox.smtp_host, mailbox.smtp_port, mailbox.smtp_security, mailbox.smtp_username, password),
                    message,
                )
            except Exception as exc:  # noqa: BLE001 -- never break the caller; the row records why
                row.attempt_count += 1
                row.updated_at = now
                row.last_error = type(exc).__name__[:255]
                if row.attempt_count >= _MAX_ATTEMPTS or isinstance(exc, smtplib.SMTPAuthenticationError):
                    row.status = "FAILED"
                else:
                    row.next_attempt_at = now + _RETRY_BACKOFF * row.attempt_count
                LOGGER.warning("cold_email_delivery_failed outbox_id=%s error=%s", outbox_id, row.last_error)
                uow.commit()
                return False
            row.attempt_count += 1
            row.status, row.last_error, row.updated_at = "SENT", None, now
            row.payload = {**row.payload, "message_id": message["Message-ID"]}
            uow.commit()
            return True


def _build_message(mailbox: EmailConnectionRow, payload: dict[str, Any]) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((mailbox.from_name, mailbox.from_address))
    message["To"] = payload["to"]
    message["Subject"] = payload["subject"]
    message["Message-ID"] = make_msgid(domain=mailbox.from_address.rsplit("@", 1)[-1])
    for name, value in (payload.get("headers") or {}).items():
        message[name] = value
    message.set_content(payload["body"])
    return message


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _sent_since(session, business_id: str, since: datetime) -> int:  # noqa: ANN001
    return int(
        session.scalar(
            select(func.count())
            .select_from(IntegrationOutboxRow)
            .where(
                IntegrationOutboxRow.business_id == business_id,
                IntegrationOutboxRow.kind == COLD_EMAIL_KIND,
                IntegrationOutboxRow.status == "SENT",
                IntegrationOutboxRow.updated_at >= since,
            )
        )
        or 0
    )


def _validate(settings: MailboxSettings) -> None:
    if not _EMAIL_RE.fullmatch(settings.from_address.strip()):
        raise EmailOutreachError("from_address must be an email address")
    if not settings.from_name.strip():
        raise EmailOutreachError("from_name is required")
    if len(settings.postal_address.strip()) < 10:
        raise EmailOutreachError("a physical postal address is required in every commercial email (CAN-SPAM)")
    if settings.smtp_security not in {"ssl", "starttls"}:
        raise EmailOutreachError("smtp_security must be ssl or starttls")
    if not settings.smtp_host.strip() or not 1 <= settings.smtp_port <= 65535:
        raise EmailOutreachError("smtp_host and smtp_port are required")
    if not settings.smtp_username.strip() or not settings.password:
        raise EmailOutreachError("smtp_username and password are required")
    if not 1 <= settings.daily_limit <= 500:
        raise EmailOutreachError("daily_limit must be between 1 and 500")
