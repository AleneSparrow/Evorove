"""Each business sends cycle-2 cold email from its own mailbox (roadmap step 13)."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.app import create_app
from src.config import Settings
from src.domain.models import utc_now
from src.domain.tenancy import Business
from src.persistence.email_outreach_service import (
    COLD_EMAIL_KIND,
    EmailOutreachError,
    EmailOutreachService,
    MailboxSettings,
    todays_cap,
)
from src.persistence.sqlalchemy_models import Base, EmailConnectionRow, IntegrationOutboxRow
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine
from tests.test_dashboard import link_business, signup_and_login

KEY = "k" * 40


def _settings(address: str = "alena@getevorove.com", **overrides) -> MailboxSettings:
    values = dict(
        from_address=address,
        from_name="Alena at Evorove",
        postal_address="100 Main St, Springfield, IL 62701",
        smtp_host="smtp.zoho.com",
        smtp_port=465,
        smtp_security="ssl",
        smtp_username=address,
        password="app-password-1",
        imap_host="imap.zoho.com",
        imap_port=993,
        daily_limit=30,
    )
    values.update(overrides)
    return MailboxSettings(**values)


@pytest.fixture
def factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'email.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    now = utc_now()
    with factory() as uow:
        uow.businesses.add(Business("evorove", "Evorove", now, now))
        uow.businesses.add(Business("salon", "Salon", now, now))
        uow.commit()
    yield factory
    engine.dispose()


class FakeSmtp:
    def __init__(self) -> None:
        self.sent: list[tuple] = []
        self.fail_with: Exception | None = None

    def __call__(self, target, message) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append((target, message))


def test_each_business_sends_from_its_own_mailbox(factory) -> None:
    smtp = FakeSmtp()
    service = EmailOutreachService(factory, encryption_key=KEY, sender=smtp)
    service.connect("evorove", _settings())
    service.connect("salon", _settings("owner@salon.example", smtp_host="smtp.gmail.com", smtp_port=587, smtp_security="starttls"))

    service.enqueue("evorove", to_address="owner@shop.example", subject="Quick question", body="Hi there", outbox_id="e1")
    service.enqueue("salon", to_address="buyer@corp.example", subject="Hello", body="Hi", outbox_id="s1")
    assert service.deliver_due() == {"attempted": 2, "sent": 2, "failed": 0}

    by_host = {target.host: (target, message) for target, message in smtp.sent}
    evorove_target, evorove_message = by_host["smtp.zoho.com"]
    assert evorove_target.password == "app-password-1" and evorove_target.security == "ssl"
    assert evorove_message["From"] == "Alena at Evorove <alena@getevorove.com>"
    assert evorove_message["To"] == "owner@shop.example"
    assert evorove_message["Message-ID"].endswith("@getevorove.com>")
    assert by_host["smtp.gmail.com"][1]["From"].endswith("<owner@salon.example>")


def test_password_is_encrypted_and_never_returned(factory) -> None:
    service = EmailOutreachService(factory, encryption_key=KEY, sender=FakeSmtp())
    status = service.connect("evorove", _settings())
    assert "password" not in repr(status)
    with factory() as uow:
        stored = uow.session.get(EmailConnectionRow, "evorove").password_encrypted
    assert "app-password-1" not in stored


def test_connecting_without_an_encryption_key_is_refused(factory) -> None:
    service = EmailOutreachService(factory, encryption_key=None, sender=FakeSmtp())
    with pytest.raises(EmailOutreachError, match="ACCOUNT_SECURITY_ENCRYPTION_KEY"):
        service.connect("evorove", _settings())


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"postal_address": "PO"}, "postal address"),
        ({"smtp_security": "none"}, "smtp_security"),
        ({"from_address": "not-an-email"}, "from_address"),
        ({"daily_limit": 0}, "daily_limit"),
    ],
)
def test_invalid_mailbox_settings_are_rejected(factory, overrides, message) -> None:
    service = EmailOutreachService(factory, encryption_key=KEY, sender=FakeSmtp())
    with pytest.raises(EmailOutreachError, match=message):
        service.connect("evorove", _settings(**overrides))


def test_warmup_ramps_up_to_the_daily_limit() -> None:
    start = utc_now()
    assert todays_cap(30, start, start) == 10
    assert todays_cap(30, start, start + timedelta(days=2)) == 20
    assert todays_cap(30, start, start + timedelta(days=30)) == 30


def test_daily_cap_holds_extra_messages_for_later(factory) -> None:
    smtp = FakeSmtp()
    service = EmailOutreachService(factory, encryption_key=KEY, sender=smtp)
    service.connect("evorove", _settings())
    for index in range(12):
        service.enqueue("evorove", to_address=f"p{index}@shop.example", subject="Hi", body="Hi", outbox_id=f"e{index}")
    result = service.deliver_due()
    assert result["sent"] == 10 and len(smtp.sent) == 10  # day-one warm-up cap
    with factory() as uow:
        held = [
            row.last_error
            for row in uow.session.scalars(
                select(IntegrationOutboxRow).where(IntegrationOutboxRow.status == "PENDING")
            ).all()
        ]
    assert held == ["daily_cap", "daily_cap"]


def test_enqueue_is_idempotent_and_needs_a_mailbox(factory) -> None:
    service = EmailOutreachService(factory, encryption_key=KEY, sender=FakeSmtp())
    with pytest.raises(EmailOutreachError, match="connect a mailbox"):
        service.enqueue("evorove", to_address="a@b.example", subject="x", body="y")
    service.connect("evorove", _settings())
    service.enqueue("evorove", to_address="a@b.example", subject="x", body="y", outbox_id="same")
    service.enqueue("evorove", to_address="a@b.example", subject="x", body="y", outbox_id="same")
    with factory() as uow:
        count = len(uow.session.scalars(select(IntegrationOutboxRow).where(IntegrationOutboxRow.kind == COLD_EMAIL_KIND)).all())
    assert count == 1


def test_smtp_failure_retries_then_gives_up(factory) -> None:
    smtp = FakeSmtp()
    smtp.fail_with = OSError("connection refused")
    service = EmailOutreachService(factory, encryption_key=KEY, sender=smtp)
    service.connect("evorove", _settings())
    service.enqueue("evorove", to_address="a@b.example", subject="x", body="y", outbox_id="r1")
    assert service.deliver_one("r1") is False
    with factory() as uow:
        row = uow.session.get(IntegrationOutboxRow, "r1")
        assert row.status == "PENDING" and row.attempt_count == 1 and row.last_error == "OSError"


def test_owner_api_hides_the_password(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    now = utc_now()
    with factory() as uow:
        uow.businesses.add(Business("evorove", "Evorove", now, now, plan="starter", subscription_status="active"))
        uow.commit()
    app = create_app(settings=Settings(database_url=database_url, app_env="test", account_security_encryption_key=KEY))
    with TestClient(app, raise_server_exceptions=False) as client:
        token = signup_and_login(client, "alena@example.com")
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        link_business(factory, business_id="evorove", user_id=me["user_id"])
        headers = {"Authorization": f"Bearer {token}"}
        body = {field: getattr(_settings(), field) for field in _settings().__slots__}
        put = client.put("/api/v1/businesses/evorove/integrations/email", json=body, headers=headers)
        assert put.status_code == 200, put.text
        assert put.json()["connected"] is True and put.json()["todays_cap"] == 10
        assert "password" not in put.text and "app-password-1" not in put.text
        other = client.get("/api/v1/businesses/evorove/integrations/email")
        assert other.status_code == 401
        deleted = client.delete("/api/v1/businesses/evorove/integrations/email", headers=headers)
        assert deleted.json() == {**deleted.json(), "connected": False}
    engine.dispose()
