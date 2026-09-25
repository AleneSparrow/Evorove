"""Google Calendar connection + booking->event mirroring (cycle 2 offline close).

FOUNDATION.md: the close is not done until the hour is in the business's own
calendar. These tests pin three things: (1) the OAuth grant is stored Fernet-
encrypted, never plaintext; (2) a BOOKED turn creates an event, a reschedule
PATCHes it, a cancel deletes it -- through the durable outbox; (3) delivery
never raises into the sales flow.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from src.domain.account_security import SecretBox
from src.persistence import calendar_service
from src.persistence.sqlalchemy_models import (
    Base,
    BookingRow,
    CalendarConnectionRow,
    CalendarEventLinkRow,
    ConversationRow,
    IntegrationOutboxRow,
    LeadRow,
    ProcessCaseRow,
)
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine
from tests.test_conversations import seed

NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
BUSINESS = "tenant-a"
KEY = "x" * 40
CLIENT_ID = "cid"
CLIENT_SECRET = "csecret"
TOKEN_URL = "https://oauth2.googleapis.com/token"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars"


class FakeGoogle:
    """Routes by URL/method and records every call, like a stubbed Google API."""

    def __init__(self, *, with_refresh_token: bool = True) -> None:
        self.calls: list[tuple[str, str]] = []
        self.with_refresh_token = with_refresh_token
        self.fail_events = False

    def __call__(self, method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, dict]:
        self.calls.append((method, url))
        if url == TOKEN_URL:
            if b"refresh_token" in (body or b""):
                return 200, {"access_token": "at-refreshed", "expires_in": 3600}
            token = {"access_token": "at-1", "expires_in": 3600}
            if self.with_refresh_token:
                token["refresh_token"] = "rt-1"
            return 200, token
        if url.startswith(EVENTS_URL):
            if self.fail_events:
                return 500, {}
            if method == "DELETE":
                return 204, {}
            return 200, {"id": "gcal-1", "status": "confirmed"}
        return 500, {}


@pytest.fixture
def service(tmp_path: Path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'calendar.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    seed(factory, BUSINESS)
    google = FakeGoogle()
    svc = calendar_service.CalendarService(
        factory,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        encryption_key=KEY,
        poster=google,
    )
    yield svc, factory, google, database_url
    engine.dispose()


def _connect(svc: calendar_service.CalendarService, business_id: str = BUSINESS) -> str:
    auth_url = svc.begin_connect(business_id, "user-1", "https://app.example/settings?tab=calendar")
    state = auth_url.split("state=")[1].split("&")[0]
    svc.complete_connect(business_id, state, "one-time-code")
    return state


def _insert_booking(factory, *, status: str = "CONFIRMED", version: int = 0, business_id: str = BUSINESS) -> str:
    start_at = NOW + timedelta(days=1, hours=2)
    end_at = start_at + timedelta(hours=1)
    with factory() as uow:
        session = uow.session
        # flush() after each add: the composite tenant FKs mean SQLAlchemy can't
        # be trusted to order these inserts itself, and SQLite enforces FKs.
        session.add(
            LeadRow(
                id="lead-1", business_id=business_id, name="Ada", phone="+13125550190",
                created_at=NOW, updated_at=NOW,
            )
        )
        session.flush()
        session.add(
            ProcessCaseRow(
                id="case-1", business_id=business_id, lead_id="lead-1",
                current_state="BOOKED", created_at=NOW, updated_at=NOW,
            )
        )
        session.flush()
        session.add(
            ConversationRow(
                id="conv-1", business_id=business_id, token_hash="t" * 64, channel="web_chat",
                lead_id="lead-1", case_id="case-1", status="ai_active",
                created_at=NOW, updated_at=NOW, last_activity_at=NOW,
                token_expires_at=NOW + timedelta(days=1),
            )
        )
        session.flush()
        session.add(
            BookingRow(
                id="booking-1", business_id=business_id, case_id="case-1", lead_id="lead-1",
                service_id="diagnostic-visit", start_at=start_at, end_at=end_at,
                timezone="America/Chicago", status=status, created_at=NOW, updated_at=NOW,
                version=version,
            )
        )
        uow.commit()
    return "booking-1"


def test_disabled_without_credentials(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'off.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    svc = calendar_service.CalendarService(
        factory, client_id=None, client_secret=None, encryption_key=None,
    )
    assert svc.enabled is False
    with pytest.raises(ValueError):
        svc.begin_connect(BUSINESS, "user-1", "https://app.example/settings")
    assert svc.deliver_due() == {"attempted": 0, "sent": 0, "failed": 0}
    engine.dispose()


def test_connect_stores_tokens_encrypted_not_plaintext(service) -> None:
    svc, factory, _, database_url = service
    _connect(svc)
    with factory() as uow:
        row = uow.session.get(CalendarConnectionRow, BUSINESS)
        assert row is not None and row.provider == "google"
        assert row.encrypted_refresh_token != "rt-1"
        assert row.encrypted_access_token != "at-1"
        assert SecretBox(KEY).decrypt(row.encrypted_refresh_token) == "rt-1"
        assert SecretBox(KEY).decrypt(row.encrypted_access_token) == "at-1"
    # The plaintext tokens must not appear anywhere in the database file.
    raw = Path(database_url.removeprefix("sqlite+pysqlite:///")).read_bytes()
    assert b"rt-1" not in raw and b"at-1" not in raw


def test_connect_rejects_grant_without_refresh_token(service) -> None:
    svc, _, google, _ = service
    google.with_refresh_token = False
    state = svc.begin_connect(BUSINESS, "user-1", "https://app.example/settings?tab=calendar")
    with pytest.raises(ValueError):
        svc.complete_connect(BUSINESS, state, "one-time-code")


def test_booking_creates_reschedules_and_deletes_the_event(service) -> None:
    svc, factory, google, _ = service
    _connect(svc)
    _insert_booking(factory)
    svc.report_conversation(BUSINESS, "conv-1")

    events = [url for method, url in google.calls if url.startswith(EVENTS_URL)]
    assert any(m == "POST" for m, _ in google.calls)
    assert events  # one create happened
    with factory() as uow:
        link = uow.session.get(CalendarEventLinkRow, "booking-1")
        assert link is not None and link.google_event_id == "gcal-1"
        assert uow.session.scalars(select(IntegrationOutboxRow.id)).one() == "calendar:booking-1:v0"

    # Reschedule: same booking row, bumped version, new slot.
    with factory() as uow:
        booking = uow.session.get(BookingRow, "booking-1")
        booking.version = 1
        booking.start_at = booking.start_at + timedelta(days=1)
        booking.end_at = booking.end_at + timedelta(days=1)
        booking.status = "RESCHEDULED"
        uow.commit()
    google.calls.clear()
    svc.report_conversation(BUSINESS, "conv-1")
    assert [m for m, _ in google.calls if m == "PATCH" and _.startswith(EVENTS_URL)]
    with factory() as uow:
        assert uow.session.get(CalendarEventLinkRow, "booking-1") is not None

    # Cancel: the mirrored event is deleted and the link row dropped.
    with factory() as uow:
        booking = uow.session.get(BookingRow, "booking-1")
        booking.version = 2
        booking.status = "CANCELLED"
        uow.commit()
    google.calls.clear()
    svc.report_conversation(BUSINESS, "conv-1")
    assert [m for m, _ in google.calls if m == "DELETE"]
    with factory() as uow:
        assert uow.session.get(CalendarEventLinkRow, "booking-1") is None


def test_no_connection_row_means_no_event_write(service) -> None:
    svc, factory, google, _ = service
    _insert_booking(factory)
    svc.report_conversation(BUSINESS, "conv-1")
    assert not [m for m, _ in google.calls if m in ("POST", "PATCH", "DELETE")]
    with factory() as uow:
        assert uow.session.scalars(select(IntegrationOutboxRow.id)).all() == []


def test_cancel_supersedes_a_pending_create(service) -> None:
    svc, factory, google, _ = service
    _connect(svc)
    _insert_booking(factory)  # CONFIRMED v0

    google.fail_events = True
    svc.report_conversation(BUSINESS, "conv-1")
    with factory() as uow:
        pending = uow.session.scalars(
            select(IntegrationOutboxRow.id).where(IntegrationOutboxRow.status == "PENDING")
        ).all()
        assert pending == ["calendar:booking-1:v0"]

    with factory() as uow:
        booking = uow.session.get(BookingRow, "booking-1")
        booking.version = 1
        booking.status = "CANCELLED"
        uow.commit()

    google.fail_events = False
    google.calls.clear()
    svc.report_conversation(BUSINESS, "conv-1")

    # The stale create was superseded (never delivered), and the delete had
    # nothing to remove, so no event write reached Google at all.
    assert not [m for m, _ in google.calls if m in ("POST", "PATCH", "DELETE")]
    with factory() as uow:
        rows = uow.session.scalars(select(IntegrationOutboxRow)).all()
        assert {r.id: r.status for r in rows} == {
            "calendar:booking-1:v0": "SENT",
            "calendar:booking-1:v1": "SENT",
        }
        assert uow.session.get(CalendarEventLinkRow, "booking-1") is None


def test_expired_access_token_is_refreshed_once(service) -> None:
    svc, factory, google, _ = service
    _connect(svc)
    _insert_booking(factory)
    with factory() as uow:
        connection = uow.session.get(CalendarConnectionRow, BUSINESS)
        connection.access_token_expires_at = NOW - timedelta(minutes=1)
        uow.commit()
    svc.report_conversation(BUSINESS, "conv-1")
    assert any(m == "POST" and u == TOKEN_URL for m, u in google.calls)
    with factory() as uow:
        connection = uow.session.get(CalendarConnectionRow, BUSINESS)
        assert SecretBox(KEY).decrypt(connection.encrypted_access_token) == "at-refreshed"


def test_disconnect_drops_connection_and_links(service) -> None:
    svc, factory, google, _ = service
    _connect(svc)
    _insert_booking(factory)
    svc.report_conversation(BUSINESS, "conv-1")
    svc.disconnect(BUSINESS)
    with factory() as uow:
        assert uow.session.get(CalendarConnectionRow, BUSINESS) is None
        assert uow.session.get(CalendarEventLinkRow, "booking-1") is None
