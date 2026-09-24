"""Cycle 2 writes first to the person on the CRM Cold tab (roadmap step 14)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.app import create_app
from src.config import Settings
from src.persistence import crm_board_service, email_outreach_service
from src.persistence.email_outreach_service import EmailOutreachError, EmailOutreachService, read_unsubscribe_token
from src.persistence.outreach_service import OutreachError, OutreachService, draft_first_email
from src.persistence.sqlalchemy_models import Base, IntegrationOutboxRow
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine
from tests.test_conversations import seed
from tests.test_dashboard import link_business, signup_and_login
from tests.test_email_outreach import KEY, FakeSmtp, _settings

SECRET = "board-secret"
CRM = "https://crm.example"
PUBLIC = "https://api.example"
REASON = "Posted on the city forum that their shop loses weekend calls"


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    posts: list[dict] = []

    def fake_post(url: str, secret: str, payload: dict):
        posts.append(payload)
        return True, None

    monkeypatch.setattr(crm_board_service, "post_internal_json", fake_post)
    monkeypatch.setattr(email_outreach_service, "in_business_quiet_hours", lambda now, dna: False)
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'outreach.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    seed(factory, "tenant-a")
    smtp = FakeSmtp()
    email = EmailOutreachService(factory, encryption_key=KEY, sender=smtp, public_base_url=PUBLIC)
    board = crm_board_service.CrmBoardService(factory, crm_base_url=CRM, secret=SECRET)
    service = OutreachService(factory, email=email, board=board)
    yield service, email, smtp, posts, factory
    engine.dispose()


def _assign(service: OutreachService, **overrides) -> str:
    values = dict(
        person_id="person-0001", email="owner@shop.example", phone=None, name="Dana Smith",
        reason=REASON, reason_source="https://forum.example/t/1",
    )
    values.update(overrides)
    return service.assign_cold("tenant-a", **values)


def test_draft_uses_only_the_reason_and_dna_facts() -> None:
    dna = {"business": {"name": "Cool Air", "description": "HVAC repair in Chicago"}, "services": [{"name": "AC repair"}]}
    draft = draft_first_email(dna, name="Dana Smith", reason=REASON, sender_name="Alena", postal_address="100 Main St, Springfield, IL")
    assert draft.subject == "Quick question for Dana"
    assert REASON in draft.body and "Cool Air — HVAC repair in Chicago." in draft.body
    assert "100 Main St, Springfield, IL" in draft.body and 'Reply "no"' in draft.body
    assert "$" not in draft.body


def test_cold_person_gets_one_draft_and_phone_only_is_skipped(world) -> None:
    service, email, *_ = world
    email.connect("tenant-a", _settings())
    assert _assign(service) == "drafted"
    assert _assign(service) == "drafted"  # handed over twice, one draft
    assert _assign(service, person_id="person-0002", email=None, phone="+13125550190") == "skipped"
    rows = {row["person_id"]: row for row in service.list("tenant-a")}
    assert len(rows) == 2
    assert rows["person-0002"]["skip_reason"] == "no_email_cold_sms_not_allowed"
    assert "100 Main St, Springfield, IL 62701" in rows["person-0001"]["body"]


def test_approved_email_leaves_the_mailbox_and_reaches_the_board(world) -> None:
    service, email, smtp, posts, _ = world
    email.connect("tenant-a", _settings())
    _assign(service)
    result = service.approve("tenant-a", "person-0001", approved_by="alena@example.com", subject="Weekend calls")
    assert result["status"] == "sent"
    (target, message), = smtp.sent
    assert message["To"] == "owner@shop.example" and message["Subject"] == "Weekend calls"
    kinds = [(p["kind"], p.get("person_id")) for p in posts]
    assert kinds == [("dialogue_started", "person-0001"), ("message", "person-0001")]
    assert posts[1]["summary"].startswith("Evorove: Weekend calls — ")
    service.sync_sent()
    assert len(posts) == 2


def test_unsafe_edit_and_missing_mailbox_are_refused(world) -> None:
    service, email, smtp, *_ = world
    _assign(service)
    with pytest.raises(OutreachError, match="mailbox"):
        service.approve("tenant-a", "person-0001", approved_by="a")
    email.connect("tenant-a", _settings())
    with pytest.raises(OutreachError, match="price"):
        service.approve("tenant-a", "person-0001", approved_by="a", body="Get 20% off, only $99")
    assert smtp.sent == [] and service.get("tenant-a", "person-0001")["status"] == "drafted"


def test_board_stop_blocks_a_pending_email(world) -> None:
    service, email, smtp, _, factory = world
    email.connect("tenant-a", _settings())
    _assign(service)
    smtp.fail_with = OSError("down")
    assert service.approve("tenant-a", "person-0001", approved_by="a")["status"] == "approved"
    assert service.stop("tenant-a", email="OWNER@shop.example", phone=None) == 1
    smtp.fail_with = None
    with factory() as uow:
        row = uow.session.get(IntegrationOutboxRow, "cold-email:tenant-a:person-0001")
        row.next_attempt_at = row.created_at
        uow.commit()
    email.deliver_due()
    assert smtp.sent == [] and service.get("tenant-a", "person-0001")["status"] == "stopped"


def test_crm_command_and_owner_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crm_board_service, "post_internal_json", lambda url, secret, payload: (True, None))
    monkeypatch.setattr(email_outreach_service, "in_business_quiet_hours", lambda now, dna: False)
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    seed(factory, "tenant-a")
    app = create_app(settings=Settings(
        database_url=database_url, app_env="test", internal_task_secret=SECRET,
        crm_base_url=CRM, account_security_encryption_key=KEY, public_api_base_url=PUBLIC,
    ))
    internal = {"X-Internal-Task-Secret": SECRET}
    command = {
        "command_id": "cold:person-0001", "person_id": "person-0001", "action": "cold_assigned",
        "payload": {"reason": REASON, "reason_source": "forum", "channel": "email"},
        "email": "owner@shop.example", "name": "Dana Smith",
    }
    with TestClient(app, raise_server_exceptions=False) as client:
        url = "/api/v1/internal/businesses/tenant-a/lead-commands"
        assert client.post(url, json=command).status_code == 401
        accepted = client.post(url, json=command, headers=internal)
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "drafted"

        token = signup_and_login(client, "alena@example.com")
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        link_business(factory, business_id="tenant-a", user_id=me["user_id"])
        headers = {"Authorization": f"Bearer {token}"}
        listed = client.get("/api/v1/businesses/tenant-a/outreach/prospects?status=drafted", headers=headers)
        assert [row["person_id"] for row in listed.json()] == ["person-0001"]
        refused = client.post("/api/v1/businesses/tenant-a/outreach/prospects/person-0001/approve", json={}, headers=headers)
        assert refused.status_code == 422 and "mailbox" in refused.text

        paused = client.post(url, json={**command, "command_id": "p1", "action": "pause_outreach"}, headers=internal)
        assert paused.json()["changed"] >= 1
        skipped = client.post("/api/v1/businesses/tenant-a/outreach/prospects/person-0001/skip", headers=headers)
        assert skipped.json()["status"] == "stopped"
    engine.dispose()


def test_every_email_carries_a_working_unsubscribe_link(world) -> None:
    service, email, smtp, *_ = world
    email.connect("tenant-a", _settings())
    _assign(service)
    service.approve("tenant-a", "person-0001", approved_by="a")
    (_, message), = smtp.sent
    link = message["List-Unsubscribe"].strip("<>")
    assert link.startswith(f"{PUBLIC}/api/v1/public/unsubscribe/")
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert f"Unsubscribe: {link}" in message.get_content()
    token = link.rsplit("/", 1)[-1]
    assert read_unsubscribe_token(KEY, token) == ("tenant-a", "owner@shop.example")
    assert read_unsubscribe_token(KEY, token[:-1] + ("0" if token[-1] != "0" else "1")) is None
    assert read_unsubscribe_token("other-key" * 5, token) is None


def test_approve_needs_the_public_url_for_the_link(world) -> None:
    _, _, smtp, _, factory = world
    no_link = EmailOutreachService(factory, encryption_key=KEY, sender=smtp)
    service = OutreachService(factory, email=no_link, board=crm_board_service.CrmBoardService(factory, crm_base_url=None, secret=None))
    no_link.connect("tenant-a", _settings())
    _assign(service)
    with pytest.raises(OutreachError, match="PUBLIC_API_BASE_URL"):
        service.approve("tenant-a", "person-0001", approved_by="a")


def test_unsubscribed_person_never_gets_anything_again(world) -> None:
    service, email, smtp, posts, factory = world
    email.connect("tenant-a", _settings())
    _assign(service)
    smtp.fail_with = OSError("down")
    service.approve("tenant-a", "person-0001", approved_by="a")  # pending, not sent yet
    assert service.unsubscribe("tenant-a", "Owner@Shop.example") is True
    assert service.unsubscribe("tenant-a", "owner@shop.example") is False
    smtp.fail_with = None
    with factory() as uow:
        row = uow.session.get(IntegrationOutboxRow, "cold-email:tenant-a:person-0001")
        row.status, row.next_attempt_at = "PENDING", row.created_at  # even a revived row is refused
        uow.commit()
    email.deliver_due()
    assert smtp.sent == []
    with factory() as uow:
        assert uow.session.get(IntegrationOutboxRow, "cold-email:tenant-a:person-0001").last_error == "suppressed"
    with pytest.raises(EmailOutreachError, match="unsubscribed"):
        email.enqueue("tenant-a", to_address="owner@shop.example", subject="x", body="y")
    assert _assign(service, person_id="person-0009") == "skipped"
    stopped = [p for p in posts if p["kind"] == "stopped"]
    assert len(stopped) == 1 and stopped[0]["person_id"] == "person-0001"
    assert stopped[0]["summary"].startswith("Unsubscribed")


def test_sms_stop_also_blocks_cold_email(world) -> None:
    service, email, *_ , factory = world
    from src.domain.models import utc_now
    from src.persistence.sqlalchemy_models import SmsSuppressionRow

    with factory() as uow:
        uow.session.add(SmsSuppressionRow(business_id="tenant-a", phone_number="+13125550190", suppressed_at=utc_now()))
        uow.commit()
    email.connect("tenant-a", _settings())
    assert _assign(service, phone="+13125550190") == "skipped"
    assert service.get("tenant-a", "person-0001")["skip_reason"] == "unsubscribed"


def test_quiet_hours_hold_the_email(world, monkeypatch: pytest.MonkeyPatch) -> None:
    service, email, smtp, _, factory = world
    email.connect("tenant-a", _settings())
    _assign(service)
    monkeypatch.setattr(email_outreach_service, "in_business_quiet_hours", lambda now, dna: True)
    assert service.approve("tenant-a", "person-0001", approved_by="a")["status"] == "approved"
    assert smtp.sent == []
    with factory() as uow:
        row = uow.session.get(IntegrationOutboxRow, "cold-email:tenant-a:person-0001")
        assert row.status == "PENDING" and row.last_error == "quiet_hours"


def test_unsubscribe_page_confirms_before_acting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[dict] = []
    monkeypatch.setattr(crm_board_service, "post_internal_json", lambda url, secret, payload: (posts.append(payload) or (True, None)))
    database_url = f"sqlite+pysqlite:///{tmp_path / 'unsub.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    seed(factory, "tenant-a")
    app = create_app(settings=Settings(
        database_url=database_url, app_env="test", internal_task_secret=SECRET,
        crm_base_url=CRM, account_security_encryption_key=KEY, public_api_base_url=PUBLIC,
    ))
    token = email_outreach_service.unsubscribe_token(KEY, "tenant-a", "owner@shop.example")
    email = EmailOutreachService(factory, encryption_key=KEY)
    with TestClient(app, raise_server_exceptions=False) as client:
        page = client.get(f"/api/v1/public/unsubscribe/{token}")
        assert page.status_code == 200 and "owner@shop.example" in page.text
        assert email.is_suppressed("tenant-a", email="owner@shop.example") is False
        done = client.post(f"/api/v1/public/unsubscribe/{token}", data={"List-Unsubscribe": "One-Click"})
        assert done.status_code == 200 and "unsubscribed" in done.text
        assert email.is_suppressed("tenant-a", email="owner@shop.example") is True
        assert [p["kind"] for p in posts] == ["stopped"]
        assert client.post("/api/v1/public/unsubscribe/forged.token").status_code == 404
    engine.dispose()
