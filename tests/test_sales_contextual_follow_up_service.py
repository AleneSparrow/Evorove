"""PersistentSalesContextualFollowUpRunner against SQLite.

Covers delivery, consent/STOP gating, ProcessState isolation, and the
stalled-lead runner staying out of a sales-owned pause.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.domain.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    MessageDirection,
    MessageRole,
)
from src.domain.events import EventType
from src.domain.models import Lead, ProcessCase, ProcessEvent
from src.domain.sales import (
    CustomerEvidence,
    CustomerSalesProfile,
    FollowUpReason,
    ObjectionStatus,
    ObjectionType,
    SalesMove,
    SalesObjection,
    SalesStage,
)
from src.domain.states import ProcessState
from src.domain.tenancy import Business
from src.engine.follow_up import decide_follow_up
from src.persistence.sales_contextual_follow_up import PersistentSalesContextualFollowUpRunner
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine

NOW = datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc)
LAST_INBOUND = NOW - timedelta(hours=25)

_BUSINESS_ID = "biz-1"
_CASE_ID = "case-1"
_CONVERSATION_ID = "conv-1"

_BUSINESS_DNA = {
    "business": {"id": _BUSINESS_ID, "name": "Acme Home Services", "timezone": "America/Chicago"},
    "communication": {"quiet_hours": {"starts": "20:00", "ends": "08:00"}},
    "sales": {"follow_up": {"delays_hours": [24, 72, 168], "maximum_attempts": 3}},
}


class FakeSmsService:
    def __init__(self, *, number: str | None = "+15005550006", suppressed: bool = False) -> None:
        self.configured = True
        self._number = number
        self._suppressed = suppressed
        self.send_calls: list[tuple[str, str, str]] = []
        self._next_sid = 1

    def get_number(self, business_id: str) -> str | None:
        return self._number

    def is_suppressed(self, business_id: str, phone_number: str) -> bool:
        return self._suppressed

    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None:
        self.send_calls.append((business_id, to_number, body))
        sid = f"SM{self._next_sid:032x}"
        self._next_sid += 1
        return sid


@pytest.fixture
def uow_factory(tmp_path: Path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'sales_follow_up.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    yield SQLAlchemyUnitOfWork.factory_for_engine(engine)
    engine.dispose()


def _seed(
    uow_factory,
    *,
    consent: bool = True,
    deferred: bool = True,
    callback: bool = False,
    human_takeover: bool = False,
) -> None:
    lead = Lead("lead-1", "Ada", None, "+15551234567", sms_consent=consent)
    case = ProcessCase(
        _CASE_ID,
        _BUSINESS_ID,
        lead,
        current_state=ProcessState.QUALIFYING,
        created_at=NOW - timedelta(days=2),
        metadata={
            "sales_follow_up_reason": (
                FollowUpReason.CALLBACK_REQUESTED.value if callback
                else FollowUpReason.OBJECTION_DEFERRED.value
            ),
        },
    )
    if callback:
        case.record(ProcessEvent(
            EventType.CALLBACK_REQUESTED,
            occurred_at=LAST_INBOUND,
            source="sales_live_turn",
            payload={"reason": "customer_requested_callback"},
        ))
    objection = SalesObjection(
        ObjectionType.NEED_TO_THINK,
        ObjectionStatus.DEFERRED,
        CustomerEvidence("msg-in", "I just need some time"),
    ) if deferred else None
    profile = CustomerSalesProfile(
        _BUSINESS_ID,
        _CASE_ID,
        stage=SalesStage.FOLLOW_UP,
        current_problem="AC stopped cooling",
        desired_outcome="working this week",
        active_objection=objection,
        last_move=(
            SalesMove.SCHEDULE_CALLBACK if callback else SalesMove.NURTURE_WITHOUT_PRESSURE
        ),
        metadata=(
            {"callback_status": "requested"} if callback else {}
        ),
    )
    conversation = Conversation(
        conversation_id=_CONVERSATION_ID,
        business_id=_BUSINESS_ID,
        token_hash="a" * 64,
        channel="webchat",
        status=(
            ConversationStatus.HUMAN_TAKEOVER_ACTIVE if human_takeover
            else ConversationStatus.AI_ACTIVE
        ),
        created_at=NOW - timedelta(days=2),
        updated_at=LAST_INBOUND,
        last_activity_at=LAST_INBOUND,
        token_expires_at=NOW + timedelta(days=30),
        lead_id=lead.lead_id,
        case_id=_CASE_ID,
    )
    inbound = ConversationMessage(
        message_id="msg-in",
        business_id=_BUSINESS_ID,
        conversation_id=_CONVERSATION_ID,
        sequence_number=1,
        direction=MessageDirection.INBOUND,
        role=MessageRole.CUSTOMER,
        text="I just need some time",
        created_at=LAST_INBOUND,
    )
    with uow_factory() as uow:
        uow.businesses.add(Business(_BUSINESS_ID, "Acme Home Services", NOW, NOW))
        uow.business_dna.add_version(_BUSINESS_ID, _BUSINESS_DNA)
        uow.leads.add(_BUSINESS_ID, lead, NOW - timedelta(days=2))
        uow.cases.add(case)
        uow.events.add_many(_BUSINESS_ID, _CASE_ID, case.event_history)
        uow.sales_profiles.add(profile, now=LAST_INBOUND)
        uow.session.flush()
        uow.conversations.add(conversation)
        uow.session.flush()
        uow.conversation_messages.add(inbound)
        uow.sms_connections.add(_BUSINESS_ID, "+15005550006", "PN_fake_sid", now=NOW)
        uow.commit()


def test_deferred_pause_sends_contextual_follow_up_without_changing_process_state(
    uow_factory,
) -> None:
    _seed(uow_factory)
    sms = FakeSmsService()
    result = PersistentSalesContextualFollowUpRunner(uow_factory, sms).run(NOW)

    assert result.follow_ups_sent == 1
    assert len(sms.send_calls) == 1
    assert "no rush" in sms.send_calls[0][2].casefold()

    with uow_factory() as uow:
        case = uow.cases.get(_BUSINESS_ID, _CASE_ID)
        profile = uow.sales_profiles.get(_BUSINESS_ID, _CASE_ID)
        events = uow.events.list_for_case(_BUSINESS_ID, _CASE_ID)
    assert case is not None
    assert case.current_state is ProcessState.QUALIFYING
    assert "follow_up_attempts_sent" not in case.metadata
    sent = [event for event in events if event.event_type == EventType.SALES_FOLLOW_UP_SENT]
    assert len(sent) == 1
    assert sent[0].payload["reason"] == FollowUpReason.OBJECTION_DEFERRED.value
    assert sent[0].payload["move"] == SalesMove.SEND_CONTEXTUAL_FOLLOW_UP.value
    assert sent[0].payload["delivered"] is True
    assert profile is not None
    assert profile.last_move is SalesMove.SEND_CONTEXTUAL_FOLLOW_UP
    assert profile.stage is SalesStage.FOLLOW_UP
    assert profile.metadata["sales_follow_up"]["attempts_sent"] == 1


def test_second_sweep_does_not_resend_the_same_attempt(uow_factory) -> None:
    _seed(uow_factory)
    sms = FakeSmsService()
    runner = PersistentSalesContextualFollowUpRunner(uow_factory, sms)
    first = runner.run(NOW)
    second = runner.run(NOW)
    assert first.follow_ups_sent == 1
    assert second.follow_ups_sent == 0
    assert len(sms.send_calls) == 1


def test_no_consent_does_not_pretend_the_message_went_out(uow_factory) -> None:
    _seed(uow_factory, consent=False)
    sms = FakeSmsService()
    result = PersistentSalesContextualFollowUpRunner(uow_factory, sms).run(NOW)
    assert result.follow_ups_sent == 0
    assert result.follow_ups_skipped_no_channel == 1
    assert sms.send_calls == []
    with uow_factory() as uow:
        events = uow.events.list_for_case(_BUSINESS_ID, _CASE_ID)
        case = uow.cases.get(_BUSINESS_ID, _CASE_ID)
    assert case is not None
    assert case.current_state is ProcessState.QUALIFYING
    assert [event for event in events if event.event_type == EventType.SALES_FOLLOW_UP_SENT] == []


def test_human_takeover_blocks_send(uow_factory) -> None:
    _seed(uow_factory, human_takeover=True)
    sms = FakeSmsService()
    result = PersistentSalesContextualFollowUpRunner(uow_factory, sms).run(NOW)
    assert result.follow_ups_sent == 0
    assert sms.send_calls == []


def test_callback_reason_is_used_when_both_callback_and_deferral_exist(uow_factory) -> None:
    _seed(uow_factory, deferred=True, callback=True)
    sms = FakeSmsService()
    PersistentSalesContextualFollowUpRunner(uow_factory, sms).run(NOW)
    with uow_factory() as uow:
        events = uow.events.list_for_case(_BUSINESS_ID, _CASE_ID)
    sent = [event for event in events if event.event_type == EventType.SALES_FOLLOW_UP_SENT]
    assert len(sent) == 1
    assert sent[0].payload["reason"] == FollowUpReason.CALLBACK_REQUESTED.value
    assert "call" in sms.send_calls[0][2].casefold()


def test_stalled_lead_runner_does_not_also_nudge_a_sales_owned_pause(uow_factory) -> None:
    _seed(uow_factory)
    with uow_factory() as uow:
        case = uow.cases.get(_BUSINESS_ID, _CASE_ID)
        dna = uow.business_dna.get_active(_BUSINESS_ID)
    assert case is not None and dna is not None
    decision = decide_follow_up(case, dna.configuration, NOW)
    assert decision.due is False
    assert decision.reason == "sales_contextual_follow_up_owns_case"
