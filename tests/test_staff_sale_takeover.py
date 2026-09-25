"""C2-2: owner cannot hop into a normal sale. Risk reply still works."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_container
from src.api.errors import install_error_handlers
from src.api.routes import internal
from src.api.routes.dashboard import get_dashboard_analytics
from src.config import Settings
from src.domain.auth import StaffUser
from src.domain.conversations import Conversation, ConversationStatus
from src.domain.models import Lead, ProcessCase, ProcessEvent
from src.domain.states import ProcessState
from src.domain.tenancy import Business
from src.persistence.errors import StaffSaleTakeoverForbidden
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine
from src.persistence.staff_action_service import StaffActionService

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
BUSINESS_ID = "biz-c2-2"
SECRET = "internal-c2-2-test-secret"
STAFF = StaffUser(
    "user-1",
    "owner@example.com",
    "owner@example.com",
    "hash",
    BUSINESS_ID,
    NOW,
    (BUSINESS_ID,),
)


def _factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'staff-sale-takeover.db'}")
    Base.metadata.create_all(engine)
    return SQLAlchemyUnitOfWork.factory_for_engine(engine), engine


def _seed(factory, *, status: ConversationStatus) -> None:
    with factory() as unit_of_work:
        unit_of_work.businesses.add(Business(BUSINESS_ID, BUSINESS_ID, NOW, NOW))
        unit_of_work.leads.add(
            BUSINESS_ID,
            Lead("lead-1", name="Ada", phone="+15551234567"),
            NOW,
        )
        state = (
            ProcessState.NEEDS_HUMAN
            if status is ConversationStatus.HUMAN_TAKEOVER_REQUESTED
            else ProcessState.QUALIFYING
        )
        case = ProcessCase(
            "case-1",
            BUSINESS_ID,
            unit_of_work.leads.get(BUSINESS_ID, "lead-1"),
            state,
            NOW,
            NOW,
        )
        unit_of_work.cases.add(case)
        unit_of_work.session.flush()
        unit_of_work.conversations.add(
            Conversation(
                conversation_id="conv-1",
                business_id=BUSINESS_ID,
                token_hash="a" * 64,
                channel="sms",
                status=status,
                created_at=NOW,
                updated_at=NOW,
                last_activity_at=NOW,
                token_expires_at=NOW.replace(year=NOW.year + 1),
                lead_id="lead-1",
                case_id="case-1",
            )
        )
        unit_of_work.commit()


def test_staff_cannot_reply_on_a_normal_sale(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        _seed(factory, status=ConversationStatus.AI_ACTIVE)
        with pytest.raises(StaffSaleTakeoverForbidden) as caught:
            StaffActionService(factory).reply(BUSINESS_ID, "conv-1", STAFF, "I'll close this.")
        assert caught.value.code == "sale_takeover_forbidden"
        with factory() as unit_of_work:
            conversation = unit_of_work.conversations.get(BUSINESS_ID, "conv-1")
            assert conversation is not None
            assert conversation.status is ConversationStatus.AI_ACTIVE
    finally:
        engine.dispose()


def test_staff_can_reply_after_risk_handoff(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        _seed(factory, status=ConversationStatus.HUMAN_TAKEOVER_REQUESTED)
        result = StaffActionService(factory).reply(
            BUSINESS_ID, "conv-1", STAFF, "We paused outreach. A person will help."
        )
        assert result.conversation.status is ConversationStatus.HUMAN_TAKEOVER_ACTIVE
    finally:
        engine.dispose()


def _internal_client(tmp_path: Path):
    factory, engine = _factory(tmp_path)
    container = SimpleNamespace(
        settings=Settings(
            database_url=str(tmp_path / "unused"),
            app_env="test",
            internal_task_secret=SECRET,
        ),
        unit_of_work_factory=factory,
    )
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(internal.router)
    app.dependency_overrides[get_container] = lambda: container
    return app, engine, factory


def test_crm_takeover_is_ignored_on_a_normal_sale(tmp_path) -> None:
    app, engine, factory = _internal_client(tmp_path)
    try:
        _seed(factory, status=ConversationStatus.AI_ACTIVE)
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/lead-commands",
                json={"command_id": "cmd-takeover", "action": "takeover", "phone": "+15551234567"},
                headers={"X-Internal-Task-Secret": SECRET},
            )
        assert response.status_code == 200, response.text
        assert response.json() == {"status": "ignored", "reason": "sale_takeover_forbidden"}
        with factory() as unit_of_work:
            conversation = unit_of_work.conversations.get(BUSINESS_ID, "conv-1")
            assert conversation is not None
            assert conversation.status is ConversationStatus.AI_ACTIVE
    finally:
        engine.dispose()


def test_crm_takeover_applies_only_after_risk_handoff(tmp_path) -> None:
    app, engine, factory = _internal_client(tmp_path)
    try:
        _seed(factory, status=ConversationStatus.HUMAN_TAKEOVER_REQUESTED)
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/lead-commands",
                json={"command_id": "cmd-takeover", "action": "takeover", "phone": "+15551234567"},
                headers={"X-Internal-Task-Secret": SECRET},
            )
        assert response.status_code == 200, response.text
        assert response.json() == {"status": "applied", "action": "takeover"}
        with factory() as unit_of_work:
            conversation = unit_of_work.conversations.get(BUSINESS_ID, "conv-1")
            assert conversation is not None
            assert conversation.status is ConversationStatus.HUMAN_TAKEOVER_ACTIVE
    finally:
        engine.dispose()


def test_human_review_rows_leave_the_conversion_denominator(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        _seed(factory, status=ConversationStatus.HUMAN_TAKEOVER_REQUESTED)
        with factory() as unit_of_work:
            unit_of_work.events.add(
                BUSINESS_ID,
                "case-1",
                ProcessEvent("BOOKING_CREATED", occurred_at=NOW),
            )
            unit_of_work.commit()
        metrics = get_dashboard_analytics(BUSINESS_ID, STAFF, factory)
        assert metrics.total_cases == 1
        assert metrics.booked_cases == 1
        assert metrics.human_review_cases == 1
        assert metrics.conversion_eligible_cases == 0
        assert metrics.booking_conversion_rate == 0.0
    finally:
        engine.dispose()
