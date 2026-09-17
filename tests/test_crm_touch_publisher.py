from src.domain.models import Lead, ProcessCase
from src.domain.sales import CustomerSalesProfile, SalesMove, SalesMoveDecision, SalesStage
from src.persistence.crm_touch_publisher import (
    HttpCrmTouchPublisher,
    NullCrmTouchPublisher,
    OutboxCrmTouchPublisher,
    RecordingCrmTouchPublisher,
    publisher_from_env,
    touch_payloads_for_turn,
)


def test_first_turn_is_opened() -> None:
    lead = Lead("lead-1", name="Ada", email="ada@example.com")
    case = ProcessCase("case-1", "biz-1", lead)
    previous = CustomerSalesProfile("biz-1", "case-1")
    decision = SalesMoveDecision(
        move=SalesMove.GREET_AND_SET_CONTEXT,
        target_stage=SalesStage.GREETING,
        reason_code="greeting",
    )
    payloads = touch_payloads_for_turn(
        case=case,
        previous=previous,
        decision=decision,
        source_message_id="msg-1",
        summary="Greeting",
    )
    assert [item["kind"] for item in payloads] == ["opened"]
    assert payloads[0]["person_id"].startswith("ppl_")
    assert payloads[0]["cycle"] == 2
    assert payloads[0]["touch_id"] == "cycle2:opened:msg-1"
    assert payloads[0]["payload"]["customer_text"] == ""
    assert payloads[0]["payload"]["engine_text"] == ""


def test_touch_carries_the_dialogue_not_only_a_status_word() -> None:
    lead = Lead("lead-1", email="ada@example.com")
    case = ProcessCase("case-1", "biz-1", lead)
    previous = CustomerSalesProfile("biz-1", "case-1")
    decision = SalesMoveDecision(
        move=SalesMove.GREET_AND_SET_CONTEXT,
        target_stage=SalesStage.GREETING,
        reason_code="greeting",
    )
    payloads = touch_payloads_for_turn(
        case=case,
        previous=previous,
        decision=decision,
        source_message_id="msg-1",
        summary="Greeting",
        customer_text="We need help closing inbound leads.",
        engine_text="Evorove for Northwind. I can show how the board fills.",
    )
    assert payloads[0]["payload"]["customer_text"] == "We need help closing inbound leads."
    assert payloads[0]["payload"]["engine_text"].startswith("Evorove for Northwind")


def test_later_turn_is_in_play() -> None:
    lead = Lead("lead-1", email="ada@example.com")
    case = ProcessCase("case-1", "biz-1", lead)
    previous = CustomerSalesProfile(
        "biz-1", "case-1", last_move=SalesMove.ASK_DISCOVERY_QUESTION
    )
    decision = SalesMoveDecision(
        move=SalesMove.PRESENT_RELEVANT_VALUE,
        target_stage=SalesStage.PRESENTATION,
        reason_code="present",
    )
    kinds = [
        item["kind"]
        for item in touch_payloads_for_turn(
            case=case,
            previous=previous,
            decision=decision,
            source_message_id="msg-2",
            summary="Offer",
        )
    ]
    assert kinds == ["in_play"]


def test_ready_to_book_is_hot_journal_not_a_close_column() -> None:
    lead = Lead("lead-1", email="ada@example.com")
    case = ProcessCase("case-1", "biz-1", lead)
    previous = CustomerSalesProfile(
        "biz-1", "case-1", last_move=SalesMove.PRESENT_RELEVANT_VALUE
    )
    decision = SalesMoveDecision(
        move=SalesMove.OFFER_BOOKING_SLOTS,
        target_stage=SalesStage.COMMITMENT,
        reason_code="book",
    )
    kinds = [
        item["kind"]
        for item in touch_payloads_for_turn(
            case=case,
            previous=previous,
            decision=decision,
            source_message_id="msg-3",
            summary="Ready",
        )
    ]
    assert kinds == ["hot"]


def test_recording_publisher_keeps_payloads() -> None:
    sink = RecordingCrmTouchPublisher()
    sink.publish("biz-1", {"kind": "message"})
    sink.publish_hot_lead("biz-1", {"handoff_id": "case-1"})
    assert sink.published == [("biz-1", {"kind": "message"})]
    assert sink.hot_leads == [("biz-1", {"handoff_id": "case-1"})]


def test_publisher_from_env_needs_url_and_secret(monkeypatch) -> None:
    monkeypatch.delenv("CRM_BASE_URL", raising=False)
    monkeypatch.delenv("INTERNAL_TASK_SECRET", raising=False)
    assert isinstance(publisher_from_env(), NullCrmTouchPublisher)
    monkeypatch.setenv("CRM_BASE_URL", "http://crm.example")
    monkeypatch.setenv("INTERNAL_TASK_SECRET", "local_development_only")
    assert isinstance(publisher_from_env(), HttpCrmTouchPublisher)


def test_http_publisher_posts_touches_and_hot_leads(monkeypatch) -> None:
    seen: list[str] = []

    def fake_urlopen(request, timeout=5):  # noqa: ANN001
        seen.append(request.full_url)

        class _Response:
            def close(self) -> None:
                return None

        return _Response()

    monkeypatch.setattr("src.persistence.crm_touch_publisher.urllib.request.urlopen", fake_urlopen)
    publisher = HttpCrmTouchPublisher("http://crm.example", "local_development_only")
    publisher.publish("biz-1", {"kind": "message"})
    publisher.publish_hot_lead("biz-1", {"handoff_id": "case-1"})
    assert seen == [
        "http://crm.example/api/v1/internal/businesses/biz-1/lead-touches",
        "http://crm.example/api/v1/internal/businesses/biz-1/hot-leads",
    ]


def test_outbox_publisher_enqueues_touches_and_skips_hot_lead(tmp_path, monkeypatch) -> None:
    from datetime import datetime, timezone

    from src.domain.tenancy import Business
    from src.persistence.sqlalchemy_models import Base, IntegrationOutboxRow
    from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine

    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'touches.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    with factory() as uow:
        uow.businesses.add(Business("biz-1", "biz-1", now, now))
        uow.commit()
    seen: list[str] = []

    def fake_urlopen(request, timeout=5):  # noqa: ANN001
        seen.append(request.full_url)

        class _Response:
            def close(self) -> None:
                return None

        return _Response()

    monkeypatch.setattr("src.persistence.crm_touch_publisher.urllib.request.urlopen", fake_urlopen)
    publisher = OutboxCrmTouchPublisher(factory, "http://crm.example", "local_development_only")
    publisher.publish("biz-1", {"touch_id": "cycle2:opened:msg-1", "kind": "opened"})
    publisher.publish_hot_lead("biz-1", {"handoff_id": "case-1"})
    with factory() as uow:
        touch = uow.session.get(IntegrationOutboxRow, "cycle2:opened:msg-1")
        hot = uow.session.get(IntegrationOutboxRow, "hot:case-1")
        assert touch is not None and touch.kind == "crm_touch" and touch.status == "SENT"
        assert hot is not None and hot.kind == "crm_hot_lead" and hot.status == "SENT"
    assert seen == [
        "http://crm.example/api/v1/internal/businesses/biz-1/lead-touches",
        "http://crm.example/api/v1/internal/businesses/biz-1/hot-leads",
    ]
    engine.dispose()
