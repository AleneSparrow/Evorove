"""Write booked hours into the tenant's own Google Calendar, durably.

FOUNDATION.md: an offline close is a real hour in the business's calendar, and
calendar sync is part of the close, not "later". The owner connects her Google
account from Settings; every BOOKED turn then mirrors the booking into her
primary calendar (create, PATCH on reschedule, DELETE on cancel) through the
same durable outbox the CRM board uses, so a crash between commit and HTTP
leaves a PENDING row for POST /api/v1/internal/integrations/deliver.

OAuth tokens never sit in this database as plaintext: the refresh and access
tokens are Fernet-encrypted with the same SecretBox key material that already
protects TOTP seeds. Delivery never raises into the sales flow. The whole
feature is off unless the operator registered a Google OAuth app herself and
set GOOGLE_CALENDAR_CLIENT_ID / GOOGLE_CALENDAR_CLIENT_SECRET plus
ACCOUNT_SECURITY_ENCRYPTION_KEY (see DEPLOY.md).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from src.domain.account_security import SecretBox
from src.domain.models import utc_now

from .sqlalchemy_models import (
    BookingRow,
    BusinessDNARow,
    CalendarConnectionRow,
    CalendarEventLinkRow,
    ConversationRow,
    IntegrationOutboxRow,
    LeadRow,
    ProcessCaseRow,
)

if TYPE_CHECKING:
    from .repositories import UnitOfWorkFactory

LOGGER = logging.getLogger("uvicorn.error")

CALENDAR_KIND = "calendar_event_write"
_MAX_ATTEMPTS = 8
_BACKOFF = timedelta(minutes=5)
_STATE_TTL = timedelta(minutes=10)
_SCOPE = "https://www.googleapis.com/auth/calendar.events"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars"
_DELETE_STATUSES = frozenset({"CANCELLED"})

Poster = Callable[[str, str, dict[str, str], bytes | None], tuple[int, dict[str, Any]]]


def post_google(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, dict[str, Any]]:
    """One Google API call. Never raises; returns (status, parsed json)."""
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            detail = {}
        return exc.code, detail
    except (urllib.error.URLError, OSError, ValueError):
        return 0, {}


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _as_utc(value: datetime) -> datetime:
    # SQLite returns DateTime(timezone=True) columns naive; re-attach UTC before
    # comparing against or serializing tz-aware datetimes.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class CalendarService:
    def __init__(
        self,
        unit_of_work_factory: "UnitOfWorkFactory",
        *,
        client_id: str | None,
        client_secret: str | None,
        encryption_key: str | None,
        poster: Poster | None = None,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self._client_id = (client_id or "").strip()
        self._client_secret = client_secret or ""
        self._box = SecretBox(encryption_key) if encryption_key else None
        master = (encryption_key or "").encode("utf-8")
        self._state_key = hmac.new(master, b"calendar-oauth-state-v1", hashlib.sha256).digest()
        self._poster = poster or post_google

    @property
    def enabled(self) -> bool:
        return bool(self._client_id and self._client_secret and self._box is not None)

    # --- owner OAuth connect/disconnect -------------------------------------

    def begin_connect(self, business_id: str, user_id: str, redirect_uri: str) -> str:
        """Sign a self-contained state token and return the Google consent URL."""
        if not self.enabled:
            raise ValueError("calendar_not_enabled")
        if not redirect_uri.startswith("https://") and not redirect_uri.startswith("http://localhost"):
            raise ValueError("calendar_redirect_not_https")
        expires_at = int((utc_now() + _STATE_TTL).timestamp())
        payload = {"b": business_id, "u": user_id, "r": redirect_uri, "e": expires_at, "n": secrets.token_hex(8)}
        body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = _b64e(hmac.new(self._state_key, body.encode("ascii"), hashlib.sha256).digest())
        query = urllib.parse.urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": _SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "state": f"{body}.{signature}",
            }
        )
        return f"{_AUTH_URL}?{query}"

    def complete_connect(self, business_id: str, state: str, code: str) -> None:
        """Exchange the one-time code and persist the encrypted grant. Raises ValueError."""
        if not self.enabled:
            raise ValueError("calendar_not_enabled")
        payload = self.verify_state(state)
        if payload["b"] != business_id:
            raise ValueError("calendar_state_mismatch")
        status, token = self._poster(
            "POST",
            _TOKEN_URL,
            {"Content-Type": "application/x-www-form-urlencoded"},
            urllib.parse.urlencode(
                {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": payload["r"],
                }
            ).encode("utf-8"),
        )
        if status != 200:
            raise ValueError("calendar_token_exchange_failed")
        refresh_token = token.get("refresh_token")
        access_token = token.get("access_token")
        if not refresh_token or not access_token:
            # Without a refresh token the grant dies in one hour; refusing to
            # store it keeps the owner on the "not connected" screen instead of
            # a connection that silently stops writing after 60 minutes.
            raise ValueError("calendar_no_refresh_token")
        assert self._box is not None
        now = utc_now()
        expires_at = now + timedelta(seconds=int(token.get("expires_in") or 3600))
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                raise ValueError("calendar_unavailable")
            row = session.get(CalendarConnectionRow, business_id)
            if row is None:
                session.add(
                    CalendarConnectionRow(
                        business_id=business_id,
                        provider="google",
                        calendar_id="primary",
                        encrypted_refresh_token=self._box.encrypt(refresh_token),
                        encrypted_access_token=self._box.encrypt(access_token),
                        access_token_expires_at=expires_at,
                        scopes=_SCOPE,
                        connected_at=now,
                        updated_at=now,
                    )
                )
            else:
                row.encrypted_refresh_token = self._box.encrypt(refresh_token)
                row.encrypted_access_token = self._box.encrypt(access_token)
                row.access_token_expires_at = expires_at
                row.calendar_id = "primary"
                row.updated_at = now
            uow.commit()

    def verify_state(self, state: str) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError("calendar_not_enabled")
        try:
            body, signature = state.split(".")
        except ValueError:
            raise ValueError("calendar_state_invalid") from None
        expected = _b64e(hmac.new(self._state_key, body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("calendar_state_invalid")
        payload = json.loads(_b64d(body).decode("utf-8"))
        if int(payload.get("e") or 0) < int(utc_now().timestamp()):
            raise ValueError("calendar_state_expired")
        return payload

    def get_connection(self, business_id: str) -> dict[str, Any] | None:
        """Connection status for the owner's settings page. Never raises."""
        try:
            with self.unit_of_work_factory() as uow:
                session = getattr(uow, "session", None)
                if session is None:
                    return None
                row = session.get(CalendarConnectionRow, business_id)
                if row is None:
                    return None
                return {
                    "connected": True,
                    "provider": row.provider,
                    "calendar_id": row.calendar_id,
                    "connected_at": _as_utc(row.connected_at).isoformat(),
                }
        except Exception:  # noqa: BLE001
            LOGGER.exception("calendar_status_error business_id=%s", business_id)
            return None

    def disconnect(self, business_id: str) -> None:
        """Drop the grant, its event mirror rows, and best-effort revoke at Google."""
        try:
            with self.unit_of_work_factory() as uow:
                session = getattr(uow, "session", None)
                if session is None:
                    return
                row = session.get(CalendarConnectionRow, business_id)
                refresh_token: str | None = None
                if row is not None and self._box is not None:
                    try:
                        refresh_token = self._box.decrypt(row.encrypted_refresh_token)
                    except ValueError:
                        refresh_token = None
                for link in session.scalars(
                    select(CalendarEventLinkRow).where(CalendarEventLinkRow.business_id == business_id)
                ).all():
                    session.delete(link)
                if row is not None:
                    session.delete(row)
                uow.commit()
            if refresh_token:
                encoded = urllib.parse.urlencode({"token": refresh_token}).encode("utf-8")
                self._poster("POST", "https://oauth2.googleapis.com/revoke", {}, encoded)
        except Exception:  # noqa: BLE001
            LOGGER.exception("calendar_disconnect_error business_id=%s", business_id)

    # --- booking -> calendar mirroring ---------------------------------------

    def report_conversation(self, business_id: str, conversation_id: str) -> None:
        """Enqueue one event write per booking of the conversation's case, then
        try to deliver. Call after the turn has committed. Never raises."""
        if not self.enabled:
            return
        try:
            enqueued = self._enqueue(business_id, conversation_id)
            for outbox_id in enqueued:
                self.deliver_one(outbox_id)
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "calendar_report_error business_id=%s conversation_id=%s", business_id, conversation_id
            )

    def _enqueue(self, business_id: str, conversation_id: str) -> list[str]:
        now = utc_now()
        enqueued: list[str] = []
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return enqueued
            if session.get(CalendarConnectionRow, business_id) is None:
                return enqueued
            conversation = session.get(ConversationRow, conversation_id)
            if conversation is None or conversation.business_id != business_id or not conversation.case_id:
                return enqueued
            case = session.get(ProcessCaseRow, conversation.case_id)
            if case is None:
                return enqueued
            bookings = session.scalars(
                select(BookingRow)
                .where(BookingRow.business_id == business_id, BookingRow.case_id == case.id)
                .order_by(BookingRow.created_at.asc())
            ).all()
            if not bookings:
                return enqueued
            lead = session.get(LeadRow, conversation.lead_id) if conversation.lead_id else None
            service_names = self._service_names(session, business_id)
            for booking in bookings:
                outbox_id = f"calendar:{booking.id}:v{booking.version}"
                if session.get(IntegrationOutboxRow, outbox_id) is not None:
                    continue
                link = session.get(CalendarEventLinkRow, booking.id)
                action = "delete" if booking.status in _DELETE_STATUSES else "upsert"
                # A newer snapshot supersedes any still-pending older one, so at
                # most one live write per booking exists and a cancel can never
                # deliver before the create it cancels -- the superseded create
                # is marked SENT and simply never runs.
                for stale in session.scalars(
                    select(IntegrationOutboxRow).where(
                        IntegrationOutboxRow.kind == CALENDAR_KIND,
                        IntegrationOutboxRow.status == "PENDING",
                        IntegrationOutboxRow.id.like(f"calendar:{booking.id}:v%"),
                        IntegrationOutboxRow.id != outbox_id,
                    )
                ).all():
                    stale.status = "SENT"
                    stale.last_error = "superseded"
                    stale.updated_at = now
                service_name = service_names.get(booking.service_id, booking.service_id)
                customer = (lead.name if lead else None) or "Customer"
                payload: dict[str, Any] = {
                    "booking_id": booking.id,
                    "case_id": case.id,
                    "google_event_id": link.google_event_id if link else None,
                    "action": action,
                    "event": {
                        "summary": f"{service_name} — {customer}",
                        "description": self._description(booking, lead, case, service_name),
                        "start": {"dateTime": booking.start_at.isoformat(), "timeZone": booking.timezone},
                        "end": {"dateTime": booking.end_at.isoformat(), "timeZone": booking.timezone},
                    },
                }
                session.add(
                    IntegrationOutboxRow(
                        id=outbox_id,
                        business_id=business_id,
                        kind=CALENDAR_KIND,
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
            uow.commit()
        return enqueued

    @staticmethod
    def _service_names(session, business_id: str) -> dict[str, str]:  # noqa: ANN001
        row = session.scalars(
            select(BusinessDNARow)
            .where(BusinessDNARow.business_id == business_id, BusinessDNARow.active.is_(True))
            .order_by(BusinessDNARow.version.desc())
        ).first()
        if row is None:
            return {}
        services = (row.configuration or {}).get("services") or []
        return {str(service.get("id")): str(service.get("name") or service.get("id")) for service in services}

    @staticmethod
    def _description(booking: BookingRow, lead: LeadRow | None, case: ProcessCaseRow, service_name: str) -> str:
        lines = ["Booked via Evorove.", f"Service: {service_name}"]
        if lead is not None:
            if lead.name:
                lines.append(f"Customer: {lead.name}")
            if lead.phone:
                lines.append(f"Phone: {lead.phone}")
            if lead.email:
                lines.append(f"Email: {lead.email}")
        lines.append(f"Case: {case.id}")
        return "\n".join(lines)

    # --- durable delivery -----------------------------------------------------

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
                        IntegrationOutboxRow.kind == CALENDAR_KIND,
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
            connection = session.get(CalendarConnectionRow, row.business_id)
            if connection is None or self._box is None:
                row.status = "FAILED"
                row.last_error = "calendar_not_connected"
                row.updated_at = utc_now()
                uow.commit()
                return False
            access_token = self._access_token(session, connection)
            if access_token is None:
                self._record_attempt(row, False, "calendar_token_refresh_failed")
                uow.commit()
                return False
            payload = dict(row.payload)
            delivered, error = self._write_event(connection, access_token, session, payload)
            if not delivered and error == "unauthorized":
                access_token = self._refresh(session, connection)
                if access_token is not None:
                    delivered, error = self._write_event(connection, access_token, session, payload)
            now = utc_now()
            if delivered:
                link = session.get(CalendarEventLinkRow, payload["booking_id"])
                if payload.get("action") == "delete":
                    if link is not None:
                        session.delete(link)
                else:
                    event_id = str(payload.get("event_id") or payload.get("google_event_id") or "").strip()
                    if link is None and event_id:
                        session.add(
                            CalendarEventLinkRow(
                                business_id=row.business_id,
                                booking_id=payload["booking_id"],
                                google_event_id=event_id,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                    elif link is not None and event_id and link.google_event_id != event_id:
                        link.google_event_id = event_id
                        link.updated_at = now
                row.status = "SENT"
                row.last_error = None
            else:
                self._record_attempt(row, False, error or "calendar_write_failed")
            row.updated_at = now
            uow.commit()
            return delivered

    def _write_event(
        self,
        connection: CalendarConnectionRow,
        access_token: str,
        session,  # noqa: ANN001
        payload: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """One create/patch/delete against the Google Events API. Never raises."""
        calendar_id = urllib.parse.quote(connection.calendar_id or "primary", safe="")
        booking_id = str(payload.get("booking_id") or "")
        link = session.get(CalendarEventLinkRow, booking_id) if booking_id else None
        event_id = str(payload.get("google_event_id") or (link.google_event_id if link else "") or "").strip()
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        if payload.get("action") == "delete":
            if not event_id:
                return True, None  # nothing was ever written; already gone
            status, _ = self._poster("DELETE", f"{_EVENTS_URL}/{calendar_id}/events/{event_id}", headers, None)
            if status == 404:
                return True, None  # already deleted on Google's side
            return 200 <= status < 300, None if 200 <= status < 300 else f"http_{status}"
        body = json.dumps(payload.get("event") or {}).encode("utf-8")
        if event_id:
            status, response = self._poster("PATCH", f"{_EVENTS_URL}/{calendar_id}/events/{event_id}", headers, body)
            if status == 404:
                # The mirror row outlived the event (manual cleanup, reconnect);
                # fall through to a fresh create so the hour is never lost.
                event_id = ""
            elif 200 <= status < 300:
                payload["event_id"] = response.get("id") or event_id
                return True, None
            elif status == 401:
                return False, "unauthorized"
            else:
                return False, f"http_{status}"
        status, response = self._poster("POST", f"{_EVENTS_URL}/{calendar_id}/events", headers, body)
        if 200 <= status < 300:
            payload["event_id"] = str(response.get("id") or "")
            return True, None
        if status == 401:
            return False, "unauthorized"
        return False, f"http_{status}" if status else "calendar_unreachable"

    def _access_token(self, session, connection: CalendarConnectionRow) -> str | None:  # noqa: ANN001
        if self._box is None:
            return None
        try:
            access_token = self._box.decrypt(connection.encrypted_access_token)
        except ValueError:
            return None
        if _as_utc(connection.access_token_expires_at) > utc_now() + timedelta(minutes=1):
            return access_token
        return self._refresh(session, connection)

    def _refresh(self, session, connection: CalendarConnectionRow) -> str | None:  # noqa: ANN001
        if self._box is None:
            return None
        try:
            refresh_token = self._box.decrypt(connection.encrypted_refresh_token)
        except ValueError:
            return None
        status, token = self._poster(
            "POST",
            _TOKEN_URL,
            {"Content-Type": "application/x-www-form-urlencoded"},
            urllib.parse.urlencode(
                {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
            ).encode("utf-8"),
        )
        if status != 200 or not token.get("access_token"):
            return None
        connection.encrypted_access_token = self._box.encrypt(str(token["access_token"]))
        if token.get("refresh_token"):
            connection.encrypted_refresh_token = self._box.encrypt(str(token["refresh_token"]))
        connection.access_token_expires_at = utc_now() + timedelta(
            seconds=int(token.get("expires_in") or 3600)
        )
        connection.updated_at = utc_now()
        return str(token["access_token"])

    @staticmethod
    def _record_attempt(row: IntegrationOutboxRow, delivered: bool, error: str) -> None:
        now = utc_now()
        row.attempt_count += 1
        row.updated_at = now
        if delivered:
            row.status = "SENT"
            row.last_error = None
        elif row.attempt_count >= _MAX_ATTEMPTS:
            row.status = "FAILED"
            row.last_error = error[:255]
        else:
            row.next_attempt_at = now + (_BACKOFF * row.attempt_count)
            row.last_error = error[:255]
