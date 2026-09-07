"""Outbound first GREET on a found person: consent and STOP are stricter than the widget."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.conversations import MessageDirection
from src.domain.found_person import FoundPersonRejected, parse_found_person
from src.domain.sales import SalesMove, SalesStage
from src.domain.states import ProcessState
from src.domain.tenancy import Business
from src.persistence.errors import OutboundFirstTouchBlocked
from src.persistence.outbound_first_touch import OutboundFirstTouchService
from src.persistence.sqlalchemy_models import Base, SmsSuppressionRow
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine


ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
BUSINESS_ID = "acme-home-services"
REASON = "Asked neighbors this week for help with a broken AC"


class FakeSms:
    def __init__(self, *, suppressed: frozenset[str] = frozenset()) -> None:
        self.sent: list[tuple[str, str]] = []
        self.suppressed = set(suppressed)

    def is_suppressed(self, business_id: str, phone_number: str) -> bool:
        del business_id
        return phone_number in self.suppressed

    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None:
        del business_id
        if to_number in self.suppressed:
            return None
        self.sent.append((to_number, body))
        return "SM_out"


def _dna(business_id: str) -> dict:
    with (ROOT / "config" / "business_dna.example.json").open(encoding="utf-8") as file:
        configuration = json.load(file)
    configuration["business"]["id"] = business_id
    return configuration


def _factory(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'outbound.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    with factory() as uow:
        uow.businesses.add(Business(BUSINESS_ID, BUSINESS_ID, NOW, NOW))
        uow.business_dna.add_version(BUSINESS_ID, _dna(BUSINESS_ID))
        uow.commit()
    return factory, engine


def _start(factory, sms: FakeSms | None = None, **overrides: object):
    values: dict[str, object] = {
        "idempotency_key": "found-ada-ac-001",
        "reason": REASON,
        "source": "cycle1-candidate-ada",
        "channel": "sms",
        "consent_basis": "prior_express_written",
        "name": "Ada",
        "phone": "+15551234567",
        "now": NOW,
    }
    values.update(overrides)
    return OutboundFirstTouchService(factory, sms_service=sms or FakeSms()).start(
        BUSINESS_ID, **values  # type: ignore[arg-type]
    )


def test_contact_dump_without_reason_is_rejected() -> None:
    with pytest.raises(FoundPersonRejected, match="grounded reason"):
        parse_found_person(
            idempotency_key="key-12345",
            reason="Ada +15551234567",
            source="scraped-list",
            channel="sms",
            consent_basis="prior_express_written",
            phone="+15551234567",
        )


def test_outbound_greet_starts_without_inbound_and_reuses_greet(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    try:
        result = _start(factory, sms)
        assert result.move is SalesMove.GREET_AND_SET_CONTEXT
        assert result.process_state is ProcessState.CONTACTED
        assert result.delivered is True
        lowered = result.message_text.casefold()
        assert "thanks for reaching out" not in lowered
        assert "you reached out" not in lowered
        assert "got your message" not in lowered
        assert "acme" in lowered or "plumbing" in lowered or "help" in lowered
        assert sms.sent and sms.sent[0][0] == "+15551234567"
        with factory() as uow:
            messages = uow.conversation_messages.list_for_conversation(
                BUSINESS_ID, result.conversation_id,
            )
            assert all(item.direction is MessageDirection.OUTBOUND for item in messages)
            assert messages[0].text == result.message_text
            profile = uow.sales_profiles.get(BUSINESS_ID, result.case_id)
            assert profile is not None
            assert profile.last_move is SalesMove.GREET_AND_SET_CONTEXT
            assert profile.stage is SalesStage.DISCOVERY
            lead = uow.leads.get(BUSINESS_ID, result.lead_id)
            assert lead is not None
            assert lead.sms_consent is True
            inbound = [
                item for item in messages if item.direction is MessageDirection.INBOUND
            ]
            assert inbound == []
    finally:
        engine.dispose()


def test_missing_consent_blocks_the_send(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    try:
        with pytest.raises(FoundPersonRejected) as caught:
            _start(factory, sms, consent_basis=None)
        assert caught.value.code == "outbound_consent_required"
        assert sms.sent == []
        with factory() as uow:
            assert uow.cases.list_for_business(BUSINESS_ID) == ()
    finally:
        engine.dispose()


def test_inferred_consent_is_not_a_send_basis(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    try:
        with pytest.raises(FoundPersonRejected) as caught:
            _start(factory, sms, consent_basis="public_post")
        assert caught.value.code == "outbound_consent_required"
        assert sms.sent == []
    finally:
        engine.dispose()


def test_stop_still_suppresses_outbound_greet(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms(suppressed=frozenset({"+15551234567"}))
    try:
        with factory() as uow:
            uow.session.add(SmsSuppressionRow(
                business_id=BUSINESS_ID,
                phone_number="+15551234567",
                suppressed_at=NOW,
            ))
            uow.commit()
        with pytest.raises(OutboundFirstTouchBlocked) as caught:
            _start(factory, sms)
        assert caught.value.code == "sms_suppressed"
        assert sms.sent == []
        with factory() as uow:
            assert uow.cases.list_for_business(BUSINESS_ID) == ()
    finally:
        engine.dispose()


def test_outbound_first_touch_is_idempotent(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    try:
        first = _start(factory, sms)
        second = _start(factory, sms)
        assert second.duplicate is True
        assert second.case_id == first.case_id
        assert second.message_text == first.message_text
        assert len(sms.sent) == 1
    finally:
        engine.dispose()
