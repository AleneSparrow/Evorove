"""Cycle 2 reports every touch to the CRM board (roadmap step 11)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.app import create_app
from src.config import Settings
from src.persistence import crm_board_service
from src.persistence.sqlalchemy_models import Base, ConversationRow, IntegrationOutboxRow
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine
from tests.test_conversations import CountingExtractor, seed

SECRET = "board-secret"
CRM = "https://crm.example"


@pytest.fixture
def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    posts: list[tuple[str, str, dict]] = []
    state = {"up": True}

    def fake_post(url: str, secret: str, payload: dict):
        posts.append((url, secret, payload))
        return (True, None) if state["up"] else (False, "unreachable")

    monkeypatch.setattr(crm_board_service, "post_internal_json", fake_post)
    database_url = f"sqlite+pysqlite:///{tmp_path / 'board.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    seed(factory, "tenant-a")
    application = create_app(
        settings=Settings(
            database_url=database_url,
            app_env="test",
            cors_allowed_origins=("https://customer.example",),
            public_chat_rate_limit_requests=100,
            internal_task_secret=SECRET,
            crm_base_url=CRM,
        ),
        intent_extractor=CountingExtractor(),
    )
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client, factory, posts, state
    engine.dispose()


def _chat(client: TestClient, message: str, external_id: str, token: str | None = None):
    if token is None:
        return client.post(
            "/api/v1/public/businesses/tenant-a/conversations",
            json={"message": message, "external_message_id": external_id},
        )
    return client.post(
        f"/api/v1/public/businesses/tenant-a/conversations/{token}/messages",
        json={"message": message, "external_message_id": external_id},
    )


def _touches(posts, kind: str | None = None) -> list[dict]:
    found = [payload for url, _, payload in posts if url.endswith("/lead-touches")]
    return [payload for payload in found if kind is None or payload["kind"] == kind]


FIRST = (
    "My AC stopped cooling and I need it working this week. "
    "AC diagnostic in 60601. My phone is +1 312 555 0190. My name is Ada"
)


def test_every_reply_reaches_the_board_with_its_text(board) -> None:
    client, _, posts, _ = board
    first = _chat(client, FIRST, "b-1")
    assert first.status_code == 200

    assert all(url.startswith(f"{CRM}/api/v1/internal/businesses/tenant-a/") for url, _, _ in posts)
    assert all(secret == SECRET for _, secret, _ in posts)
    assert len(_touches(posts, "dialogue_started")) == 1
    messages = _touches(posts, "message")
    assert [m["payload"]["direction"] for m in messages] == ["inbound", "outbound"]
    assert messages[0]["summary"].startswith("Customer: My AC stopped cooling")
    assert messages[1]["summary"].startswith("Evorove: ")
    assert messages[0]["identity"]["phone"] == "+13125550190"
    assert {m["cycle"] for m in messages} == {2} and {m["source"] for m in messages} == {"evorove"}


def test_reporting_again_sends_nothing_twice(board) -> None:
    client, factory, posts, _ = board
    token = _chat(client, FIRST, "b-1").json()["conversation_token"]
    _chat(client, "That's the issue", "b-2", token)
    ids = [payload["touch_id"] for payload in _touches(posts)]
    assert len(ids) == len(set(ids))

    with factory() as uow:
        conversation_id = uow.session.scalars(select(ConversationRow.id)).one()
    before = len(posts)
    service = crm_board_service.CrmBoardService(factory, crm_base_url=CRM, secret=SECRET)
    service.report_conversation("tenant-a", conversation_id)
    assert len(posts) == before


def test_ready_customer_becomes_offer_ready_and_a_hot_lead(board) -> None:
    client, _, posts, _ = board
    token = _chat(client, FIRST, "b-1").json()["conversation_token"]
    for index, text in enumerate(("That's the issue", "Yes", "Sounds good", "Yes, book me"), start=2):
        response = _chat(client, text, f"b-{index}", token)
    assert response.json()["current_state"] == "QUALIFIED"

    assert len(_touches(posts, "offer_sent")) == 1
    assert len(_touches(posts, "ready_to_book")) == 1
    hot = [payload for url, _, payload in posts if url.endswith("/hot-leads")]
    assert len(hot) == 1
    assert hot[0]["readiness"] == {"signal": "ready_to_book", "evidence_excerpt": "Yes, book me"}
    assert hot[0]["channel"] == "web_chat" and hot[0]["source"] == "evorove"
    assert hot[0]["service_id"]
    assert not {"slot_start_at", "start_at", "booking_id", "end_at"} & set(hot[0])


def test_anonymous_visitor_is_not_reported_until_addressable(board) -> None:
    client, _, posts, _ = board
    token = _chat(client, "Hi, my AC stopped cooling", "a-1").json()["conversation_token"]
    assert posts == []
    _chat(client, "My phone is +1 312 555 0190. My name is Ada", "a-2", token)
    assert [m["payload"]["sequence"] for m in _touches(posts, "message")][:2] == [1, 2]


def test_crm_outage_leaves_pending_rows_that_the_sweep_delivers(board) -> None:
    client, factory, posts, state = board
    state["up"] = False
    _chat(client, FIRST, "b-1")
    with factory() as uow:
        pending = uow.session.scalars(
            select(IntegrationOutboxRow).where(IntegrationOutboxRow.status == "PENDING")
        ).all()
        assert pending and {row.kind for row in pending} == {crm_board_service.TOUCH_KIND}
        for row in pending:
            row.next_attempt_at = row.created_at
        uow.commit()

    state["up"] = True
    swept = client.post("/api/v1/internal/integrations/deliver", headers={"X-Internal-Task-Secret": SECRET})
    assert swept.status_code == 200
    assert swept.json()["failed"] == 0 and swept.json()["sent"] >= 3


def test_board_commands_pause_the_engine_idempotently(board) -> None:
    client, factory, _, _ = board
    token = _chat(client, FIRST, "b-1").json()["conversation_token"]
    body = {"command_id": "cmd-1", "action": "pause_outreach", "phone": "+13125550190", "payload": {}}
    headers = {"X-Internal-Task-Secret": SECRET}

    assert client.post("/api/v1/internal/businesses/tenant-a/lead-commands", json=body).status_code == 401
    first = client.post("/api/v1/internal/businesses/tenant-a/lead-commands", json=body, headers=headers)
    again = client.post("/api/v1/internal/businesses/tenant-a/lead-commands", json=body, headers=headers)
    assert first.json()["changed"] == 1 and again.json()["changed"] == 0

    with factory() as uow:
        assert uow.session.scalars(select(ConversationRow.status)).one() == "human_takeover_active"
    reply = _chat(client, "Hello?", "b-2", token)
    assert reply.json()["status"] == "human_takeover_active"


def test_disabled_without_crm_base_url(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'off.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    service = crm_board_service.CrmBoardService(factory, crm_base_url=None, secret=SECRET)
    assert service.enabled is False
    service.report_conversation("tenant-a", "missing")
    assert service.deliver_due() == {"attempted": 0, "sent": 0, "failed": 0}
    engine.dispose()
