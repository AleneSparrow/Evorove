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


class FakeWhatsApp:
    def __init__(
        self, *, suppressed: frozenset[str] = frozenset(), configured: bool = True,
    ) -> None:
        self.sent: list[tuple[str, str]] = []
        self.suppressed = set(suppressed)
        self.configured = configured

    def is_suppressed(self, business_id: str, phone_number: str) -> bool:
        del business_id
        return phone_number in self.suppressed

    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None:
        del business_id
        if not self.configured or to_number in self.suppressed:
            return None
        self.sent.append((to_number, body))
        return "WA_out"


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


def _start(factory, sms: FakeSms | None = None, whatsapp: FakeWhatsApp | None = None, **overrides: object):
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
    return OutboundFirstTouchService(
        factory,
        sms_service=sms or FakeSms(),
        whatsapp_mouth=whatsapp,
    ).start(
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
        assert "evorove for acme home services" in lowered
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
            assert lead.attributes.get("gender") is None
            assert lead.attributes.get("region") is None
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


def test_whatsapp_preferred_is_kept_without_whatsapp_send(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    try:
        result = _start(
            factory,
            sms,
            preferred_channel="whatsapp",
            messenger_id="wa:15551234567",
            person_id="crm-found-ada-001",
        )
        assert result.delivered is True
        assert sms.sent and sms.sent[0][0] == "+15551234567"
        assert "evorove for acme home services" in result.message_text.casefold()
        with factory() as uow:
            lead = uow.leads.get(BUSINESS_ID, result.lead_id)
            assert lead is not None
            assert lead.attributes["preferred_channel"] == "whatsapp"
            assert lead.attributes["messenger_id"] == "wa:15551234567"
            assert lead.attributes["person_id"] == "crm-found-ada-001"
            assert lead.attributes["outbound_channel"] == "sms"
            assert "gender" not in lead.attributes
            assert "region" not in lead.attributes
            profile = uow.sales_profiles.get(BUSINESS_ID, result.case_id)
            assert profile is not None
            assert profile.preferred_channel == "whatsapp"
    finally:
        engine.dispose()


def test_stated_gender_and_region_are_stored_on_the_lead(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        result = _start(factory, gender="Woman", region="Illinois")
        with factory() as uow:
            lead = uow.leads.get(BUSINESS_ID, result.lead_id)
            assert lead is not None
            assert lead.attributes["gender"] == "Woman"
            assert lead.attributes["region"] == "Illinois"
    finally:
        engine.dispose()


def test_whatsapp_as_send_channel_uses_evorove_mouth(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    whatsapp = FakeWhatsApp()
    try:
        result = _start(
            factory,
            sms,
            whatsapp,
            channel="whatsapp",
            consent_basis="whatsapp_opt_in",
        )
        assert result.delivered is True
        assert sms.sent == []
        assert whatsapp.sent and whatsapp.sent[0][0] == "+15551234567"
        assert "evorove for acme home services" in result.message_text.casefold()
        with factory() as uow:
            conversation = uow.conversations.get(BUSINESS_ID, result.conversation_id)
            assert conversation is not None
            assert conversation.channel == "whatsapp"
            assert conversation.external_session_id == "wa:+15551234567"
            lead = uow.leads.get(BUSINESS_ID, result.lead_id)
            assert lead is not None
            assert lead.sms_consent is False
            assert lead.attributes["outbound_channel"] == "whatsapp"
            assert lead.attributes["outbound_consent_basis"] == "whatsapp_opt_in"
    finally:
        engine.dispose()


def test_whatsapp_stop_blocks_first_touch(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    whatsapp = FakeWhatsApp(suppressed=frozenset({"+15551234567"}))
    try:
        with pytest.raises(OutboundFirstTouchBlocked) as caught:
            _start(
                factory,
                sms,
                whatsapp,
                channel="whatsapp",
                consent_basis="whatsapp_opt_in",
            )
        assert caught.value.code == "sms_suppressed"
        assert sms.sent == []
        assert whatsapp.sent == []
    finally:
        engine.dispose()


def test_whatsapp_send_requires_evorove_mouth(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    sms = FakeSms()
    try:
        with pytest.raises(OutboundFirstTouchBlocked) as caught:
            _start(
                factory,
                sms,
                FakeWhatsApp(configured=False),
                channel="whatsapp",
                consent_basis="whatsapp_opt_in",
            )
        assert caught.value.code == "whatsapp_not_configured"
        assert sms.sent == []
    finally:
        engine.dispose()


# Pain first, then touch (owner rule, 26 October 2026).

PAIN = "Recent reviews say AC repair requests sit unanswered overnight and people book elsewhere"


class _Generated:
    def __init__(self, output) -> None:
        self.output = output


class PainCitingGenerator:
    """Stands in for the model: opens with the observed pain and cites it."""

    def __init__(self, *, cite_pain: bool = True) -> None:
        self.cite_pain = cite_pain
        self.inputs: list = []

    def generate(self, value):
        from src.ai.sales_response_models import SalesResponseOutput

        self.inputs.append(value)
        return _Generated(SalesResponseOutput(
            move=value.approved_move,
            message_text=(
                "Noticed AC requests can sit overnight, and by morning people have booked "
                "someone else. Evorove for Acme Home Services answers right away. Worth a look?"
            ),
            knowledge_ids=[],
            business_fact_ids=[],
            customer_evidence_ids=["observed-pain"] if self.cite_pain else [],
            used_safe_fallback=False,
        ))


def _start_with_generator(factory, generator, **overrides: object):
    from src.persistence.sales_live_turn import SalesLiveTurnService

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
    return OutboundFirstTouchService(
        factory,
        sms_service=FakeSms(),
        sales_live=SalesLiveTurnService(
            response_generator=generator, crm_touch_publisher=_NoCrm(),
        ),
    ).start(BUSINESS_ID, **values)  # type: ignore[arg-type]


class _NoCrm:
    def publish(self, business_id: str, payload) -> None:
        del business_id, payload


def _greet_validation(factory, result) -> dict:
    with factory() as uow:
        turns = uow.sales_turns.list_for_case(BUSINESS_ID, result.case_id)
    assert len(turns) == 1
    return dict(turns[0].validation)


def test_observed_pain_leads_the_first_touch(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    generator = PainCitingGenerator()
    try:
        result = _start_with_generator(factory, generator, observed_pain=PAIN)
        assert result.message_text.startswith("Noticed AC requests can sit overnight")
        sent = generator.inputs[0]
        assert {"evidence_id": "observed-pain", "text": PAIN} in list(sent.customer_evidence)
        assert sent.conversation_context["first_touch"] == "pain_first"
        validation = _greet_validation(factory, result)
        assert validation["first_touch_basis"] == "observed_pain"
        assert validation["pain_first_applied"] is True
        with factory() as uow:
            conversation = uow.conversations.get(BUSINESS_ID, result.conversation_id)
            assert conversation is not None
            assert conversation.metadata["first_touch_basis"] == "observed_pain"
            assert conversation.metadata["observed_pain"] == PAIN
            lead = uow.leads.get(BUSINESS_ID, result.lead_id)
            assert lead is not None
            assert lead.attributes["observed_pain"] == PAIN
    finally:
        engine.dispose()


def test_pain_that_the_wording_ignored_is_not_counted_as_pain_first(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        result = _start_with_generator(
            factory, PainCitingGenerator(cite_pain=False), observed_pain=PAIN,
        )
        validation = _greet_validation(factory, result)
        assert validation["first_touch_basis"] == "observed_pain"
        assert validation["pain_first_applied"] is False
    finally:
        engine.dispose()


def test_card_without_pain_is_marked_offer_led(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    generator = PainCitingGenerator(cite_pain=False)
    try:
        result = _start_with_generator(factory, generator)
        assert generator.inputs[0].conversation_context["first_touch"] == "offer_only"
        assert all(
            item["evidence_id"] != "observed-pain"
            for item in generator.inputs[0].customer_evidence
        )
        validation = _greet_validation(factory, result)
        assert validation["first_touch_basis"] == "offer"
        assert validation["pain_first_applied"] is False
        with factory() as uow:
            conversation = uow.conversations.get(BUSINESS_ID, result.conversation_id)
            assert conversation is not None
            assert conversation.metadata["first_touch_basis"] == "offer"
            assert "observed_pain" not in conversation.metadata
    finally:
        engine.dispose()


def test_model_cannot_cite_pain_that_was_not_supplied(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        result = _start_with_generator(factory, PainCitingGenerator(cite_pain=True))
        validation = _greet_validation(factory, result)
        assert "unknown_customer_evidence_id" in validation["violations"]
        assert validation["pain_first_applied"] is False
        assert "evorove for acme home services" in result.message_text.casefold()
    finally:
        engine.dispose()


def test_replaying_a_card_without_pain_keeps_its_idempotency(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        first = _start(factory)
        again = _start(factory)
        assert again.duplicate is True
        assert again.case_id == first.case_id
    finally:
        engine.dispose()
