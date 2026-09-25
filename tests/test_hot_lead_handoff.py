from src.domain.hot_lead_handoff import (
    build_hot_lead_handoff_payload,
    try_build_hot_lead_handoff_payload,
    waiting_channel,
)


def test_widget_channel_maps_to_web_chat() -> None:
    assert waiting_channel("webchat") == "web_chat"
    assert waiting_channel("widget") == "web_chat"
    assert waiting_channel("sms") == "sms"
    assert waiting_channel("whatsapp") == "sms"
    assert waiting_channel("wa") == "sms"


def test_ready_to_book_payload_has_no_slot() -> None:
    payload = build_hot_lead_handoff_payload(
        handoff_id="evorove-case-1",
        channel="web_chat",
        service_id="diagnostic-visit",
        evidence_excerpt="Yes, book me.",
        name="Ada",
        phone="+13125550100",
        sales_profile_snapshot={"stage": "BOOKING", "last_move": "OFFER_BOOKING_SLOTS"},
        customer_location="60601",
    )
    assert payload["source"] == "evorove"
    assert payload["readiness"]["signal"] == "ready_to_book"
    assert "booking_id" not in payload
    assert "slot_start_at" not in payload
    assert payload["identity"]["phone"] == "+13125550100"
    assert payload["service_id"] == "diagnostic-visit"


def test_builder_rejects_a_snapshot_that_already_has_an_hour() -> None:
    try:
        build_hot_lead_handoff_payload(
            handoff_id="evorove-case-1",
            channel="sms",
            service_id="diagnostic-visit",
            evidence_excerpt="Yes, book me.",
            phone="+13125550100",
            sales_profile_snapshot={"start_at": "2026-09-08T15:00:00+00:00"},
        )
    except ValueError as exc:
        assert "calendar" in str(exc)
    else:
        raise AssertionError("expected calendar snapshot to be rejected")


def test_builder_rejects_a_contact_without_a_channel() -> None:
    try:
        build_hot_lead_handoff_payload(
            handoff_id="evorove-case-1",
            channel="email",
            service_id="diagnostic-visit",
            evidence_excerpt="Yes, book me.",
            name="Ada",
        )
    except ValueError as exc:
        assert "addressable" in str(exc)
    else:
        raise AssertionError("expected missing phone/email to be rejected")


def test_incomplete_ready_to_book_does_not_shape_a_payload() -> None:
    assert try_build_hot_lead_handoff_payload(
        handoff_id="evorove-case-1",
        channel="webchat",
        service_id=None,
        evidence_excerpt="Yes, book me.",
        phone="+13125550100",
    ) is None


def test_ready_to_book_posts_hot_lead_without_a_slot() -> None:
    from datetime import datetime, timezone

    from src.domain.conversations import Conversation, ConversationStatus
    from src.domain.models import Lead, ProcessCase
    from src.domain.qualification import QualificationReasonCode, QualificationResult
    from src.domain.states import ProcessState
    from src.persistence.crm_touch_publisher import RecordingCrmTouchPublisher
    from src.persistence.sales_live_turn import _stamp_hot_lead_handoff

    now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    lead = Lead("lead-1", name="Ada", phone="+13125550100")
    case = ProcessCase("case-1", "biz-1", lead)
    conversation = Conversation(
        conversation_id="conv-1",
        business_id="biz-1",
        token_hash="a" * 64,
        channel="whatsapp",
        status=ConversationStatus.AI_ACTIVE,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
        token_expires_at=now.replace(year=2027),
    )
    recorder = RecordingCrmTouchPublisher()
    qualification = QualificationResult(
        qualified=True,
        reasons=("Ready",),
        reason_codes=(QualificationReasonCode.QUALIFIED,),
        missing_fields=(),
        unanswered_questions=(),
        confidence=1.0,
        recommended_next_state=ProcessState.QUALIFIED,
        requires_human=False,
        booking_allowed=True,
        service_id="diagnostic-visit",
    )
    _stamp_hot_lead_handoff(
        case,
        conversation=conversation,
        qualification=qualification,
        evidence_excerpt="Yes, book me.",
        last_move="OFFER_BOOKING_SLOTS",
        sales_stage="BOOKING",
        publisher=recorder,
    )
    assert recorder.hot_leads and recorder.hot_leads[0][0] == "biz-1"
    payload = recorder.hot_leads[0][1]
    assert payload["handoff_id"] == "case-1"
    assert payload["channel"] == "sms"
    assert payload["readiness"]["signal"] == "ready_to_book"
    assert "booking_id" not in payload
    assert "slot_start_at" not in payload
    _stamp_hot_lead_handoff(
        case,
        conversation=conversation,
        qualification=qualification,
        evidence_excerpt="Yes, book me.",
        last_move="OFFER_BOOKING_SLOTS",
        sales_stage="BOOKING",
        publisher=recorder,
    )
    assert len(recorder.hot_leads) == 1
