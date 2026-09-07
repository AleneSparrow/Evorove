"""SMS and staff REST intake stay sales-led: completeness is not a sale."""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.domain.qualification import IncomingMessage, IntentResult
from src.domain.states import ProcessState
from src.domain.tenancy import Business
from src.engine.intent_extractor import DeterministicIntentExtractor
from src.engine.question_generator import DeterministicQuestionGenerator
from src.persistence.lead_intake import PersistentLeadIntakeService
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine


ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
COMPLETE_TEXT = (
    "My AC stopped cooling and I need it working this week. "
    "AC diagnostic in 60601. My phone is +1 312 555 0190. My name is Ada"
)


def _dna(business_id: str) -> dict:
    with (ROOT / "config" / "business_dna.example.json").open(encoding="utf-8") as file:
        configuration = json.load(file)
    configuration["business"]["id"] = business_id
    return configuration


def _seed(factory, business_id: str = "acme-home-services") -> None:
    with factory() as uow:
        uow.businesses.add(Business(business_id, business_id, NOW, NOW))
        uow.business_dna.add_version(business_id, _dna(business_id))
        uow.commit()


def _intake(factory, results: dict[str, IntentResult] | None = None) -> PersistentLeadIntakeService:
    extractor = (
        DeterministicIntentExtractor(results)
        if results is not None
        else DeterministicIntentExtractor()
    )
    return PersistentLeadIntakeService(
        factory,
        extractor,
        DeterministicQuestionGenerator(),
    )


def _message(external_id: str, text: str = COMPLETE_TEXT, **changes: object) -> IncomingMessage:
    values: dict[str, object] = {
        "business_id": "acme-home-services",
        "channel": "sms",
        "external_message_id": external_id,
        "customer_name": "Ada",
        "phone": "+1 312 555 0190",
        "raw_text": text,
        "timestamp": NOW,
    }
    values.update(changes)
    return IncomingMessage(**values)  # type: ignore[arg-type]


def _factory(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'sales-led.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    _seed(factory)
    return factory, engine


def test_sales_led_complete_form_does_not_qualify(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    intake = _intake(factory, {"complete": IntentResult(
        service_requested="diagnostic-visit",
        customer_location="60601",
        confidence=0.95,
    )})
    try:
        result = intake.receive(_message("complete"), sales_led_conversation=True)
        assert result.current_state is ProcessState.QUALIFYING
        assert result.qualification.qualified is True
        assert result.response is not None
        assert "Choose an appointment time" not in result.response.message_text
        with factory() as uow:
            case = uow.cases.get("acme-home-services", result.case_id)
            assert case is not None
            assert case.current_state is ProcessState.QUALIFYING
    finally:
        engine.dispose()


def test_form_completeness_path_still_qualifies_when_not_sales_led(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    intake = _intake(factory, {"legacy": IntentResult(
        service_requested="diagnostic-visit",
        customer_location="60601",
        confidence=0.95,
    )})
    try:
        result = intake.receive(_message("legacy"))
        assert result.current_state is ProcessState.QUALIFIED
        assert result.qualification.qualified is True
    finally:
        engine.dispose()


def test_sales_led_sms_cycle_books_only_after_commitment(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    intake = _intake(factory)
    phone = "+1 312 555 0190"
    try:
        first = intake.receive(
            _message("sms-1", phone=phone),
            sales_led_conversation=True,
        )
        assert first.current_state is ProcessState.QUALIFYING
        confirmed = intake.receive(
            _message("sms-2", "That's the issue", phone=phone, case_id=first.case_id),
            sales_led_conversation=True,
        )
        presented = intake.receive(
            _message("sms-3", "Yes", phone=phone, case_id=first.case_id),
            sales_led_conversation=True,
        )
        asked = intake.receive(
            _message("sms-4", "Sounds good", phone=phone, case_id=first.case_id),
            sales_led_conversation=True,
        )
        assert confirmed.current_state is presented.current_state is ProcessState.QUALIFYING
        assert asked.current_state is ProcessState.QUALIFYING
        assert asked.response is not None
        assert "Choose an appointment time" not in asked.response.message_text

        offered = intake.receive(
            _message("sms-5", "Yes, book me", phone=phone, case_id=first.case_id),
            sales_led_conversation=True,
        )
        assert offered.current_state is ProcessState.QUALIFIED
        assert offered.response is not None
        assert "Choose an appointment time" in offered.response.message_text

        booked = intake.receive(
            _message("sms-6", "The second option works", phone=phone, case_id=first.case_id),
            sales_led_conversation=True,
        )
        assert booked.current_state is ProcessState.BOOKED
        assert booked.response is not None
        assert "confirmed" in booked.response.message_text.casefold()
    finally:
        engine.dispose()


def test_sales_led_duplicate_replay_keeps_sales_reply(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    intake = _intake(factory, {"dup": IntentResult(
        service_requested="diagnostic-visit",
        customer_location="60601",
        confidence=0.95,
    )})
    message = _message("dup")
    try:
        first = intake.receive(message, sales_led_conversation=True)
        duplicate = intake.receive(message, sales_led_conversation=True)
        assert first.current_state is ProcessState.QUALIFYING
        assert duplicate.duplicate
        assert duplicate.case_id == first.case_id
        assert duplicate.current_state is first.current_state
        assert duplicate.response is not None
        assert first.response is not None
        assert duplicate.response.message_text == first.response.message_text
    finally:
        engine.dispose()
