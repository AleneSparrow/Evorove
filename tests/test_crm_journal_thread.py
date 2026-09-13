"""Cycle 2 journal: GREET opens the card; a reply stays on the same live turn."""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.domain.qualification import IncomingMessage
from src.domain.tenancy import Business
from src.engine.intent_extractor import DeterministicIntentExtractor
from src.engine.question_generator import DeterministicQuestionGenerator
from src.persistence.crm_touch_publisher import RecordingCrmTouchPublisher
from src.persistence.lead_intake import PersistentLeadIntakeService
from src.persistence.outbound_first_touch import OutboundFirstTouchService
from src.persistence.sales_live_turn import SalesLiveTurnService
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine


ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
BUSINESS_ID = "acme-home-services"
REASON = "Asked neighbors this week for help with a broken AC"


class FakeSms:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def is_suppressed(self, business_id: str, phone_number: str) -> bool:
        del business_id, phone_number
        return False

    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None:
        del business_id
        self.sent.append((to_number, body))
        return "SM_out"


def _dna(business_id: str) -> dict:
    with (ROOT / "config" / "business_dna.example.json").open(encoding="utf-8") as file:
        configuration = json.load(file)
    configuration["business"]["id"] = business_id
    return configuration


def test_found_greet_then_reply_emits_opened_then_in_play(tmp_path) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'journal.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    with factory() as uow:
        uow.businesses.add(Business(BUSINESS_ID, BUSINESS_ID, NOW, NOW))
        uow.business_dna.add_version(BUSINESS_ID, _dna(BUSINESS_ID))
        uow.commit()
    recorder = RecordingCrmTouchPublisher()
    sms = FakeSms()
    first = OutboundFirstTouchService(
        factory,
        sms_service=sms,
        sales_live=SalesLiveTurnService(crm_touch_publisher=recorder),
    ).start(
        BUSINESS_ID,
        idempotency_key="found-ada-ac-001",
        reason=REASON,
        source="open-web-neighbor-post",
        channel="sms",
        consent_basis="prior_express_written",
        name="Ada",
        phone="+15551234567",
        person_id="ppl_ada_found_01",
        now=NOW,
    )
    assert [item[1]["kind"] for item in recorder.published] == ["opened"]
    with factory() as uow:
        conversation = uow.conversations.get(BUSINESS_ID, first.conversation_id)
        assert conversation is not None
        assert conversation.external_session_id == "+15551234567"

    intake = PersistentLeadIntakeService(
        factory,
        DeterministicIntentExtractor(),
        DeterministicQuestionGenerator(),
        crm_touch_publisher=recorder,
    )
    reply = intake.receive(
        IncomingMessage(
            business_id=BUSINESS_ID,
            channel="sms",
            external_message_id="SM_reply_1",
            raw_text="The AC still will not cool. Can you help this week?",
            timestamp=NOW,
            phone="+15551234567",
        ),
        sales_led_conversation=True,
    )
    assert reply.case_id == first.case_id
    assert reply.duplicate is False
    assert [item[1]["kind"] for item in recorder.published] == ["opened", "in_play"]
    assert recorder.hot_leads == []
    engine.dispose()
