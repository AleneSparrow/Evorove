from datetime import datetime, timedelta, timezone

from src.domain.sales import FollowUpReason, SalesMove, SalesStage
from src.domain.states import ProcessState
from src.engine.sales_contextual_follow_up import (
    DEFAULT_CADENCE_HOURS,
    IMPLEMENTED_REASONS,
    ContextualFollowUpSnapshot,
    cadence_from_config,
    decide_contextual_follow_up,
    phrase_contextual_follow_up,
    timezone_from_sources,
)


NOW = datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc)
LAST_INBOUND = NOW - timedelta(hours=25)


def _snapshot(**overrides: object) -> ContextualFollowUpSnapshot:
    values = {
        "process_state": ProcessState.QUALIFYING,
        "sales_stage": SalesStage.FOLLOW_UP,
        "callback_requested": False,
        "objection_deferred": True,
        "preferred_contact_at": None,
        "last_inbound_at": LAST_INBOUND,
        "last_sales_follow_up_at": None,
        "attempts_sent": 0,
        "sms_consent": True,
        "has_phone": True,
        "sms_suppressed": False,
        "human_owns": False,
        "timezone_name": "America/Chicago",
        "quiet_hours": ("20:00", "08:00"),
        "cadence_hours": DEFAULT_CADENCE_HOURS,
        "maximum_attempts": 3,
    }
    values.update(overrides)
    return ContextualFollowUpSnapshot(**values)  # type: ignore[arg-type]


def test_deferred_objection_is_due_after_cadence_with_sendable_channel() -> None:
    decision = decide_contextual_follow_up(_snapshot(), NOW)
    assert decision.due is True
    assert decision.sendable is True
    assert decision.follow_up_reason is FollowUpReason.OBJECTION_DEFERRED
    assert decision.approved_move is SalesMove.SEND_CONTEXTUAL_FOLLOW_UP
    assert decision.attempt_number == 1
    assert "no rush" in phrase_contextual_follow_up(decision.follow_up_reason).casefold()


def test_deferred_objection_is_not_due_before_cadence() -> None:
    decision = decide_contextual_follow_up(
        _snapshot(last_inbound_at=NOW - timedelta(hours=5)),
        NOW,
    )
    assert decision.due is False
    assert decision.skip_code == "delay_not_elapsed"


def test_missing_consent_does_not_pretend_a_message_was_sent() -> None:
    decision = decide_contextual_follow_up(_snapshot(sms_consent=False), NOW)
    assert decision.due is False
    assert decision.sendable is False
    assert decision.skip_code == "no_sms_consent"
    assert decision.approved_move is None


def test_stop_suppression_blocks_send() -> None:
    decision = decide_contextual_follow_up(_snapshot(sms_suppressed=True), NOW)
    assert decision.due is False
    assert decision.skip_code == "sms_suppressed"


def test_callback_beats_deferred_and_waits_for_promised_time() -> None:
    promised = NOW + timedelta(hours=2)
    decision = decide_contextual_follow_up(
        _snapshot(
            callback_requested=True,
            objection_deferred=True,
            preferred_contact_at=promised,
        ),
        NOW,
    )
    assert decision.due is False
    assert decision.follow_up_reason is FollowUpReason.CALLBACK_REQUESTED
    assert decision.skip_code == "delay_not_elapsed"

    later = decide_contextual_follow_up(
        _snapshot(
            callback_requested=True,
            objection_deferred=True,
            preferred_contact_at=NOW - timedelta(minutes=5),
        ),
        NOW,
    )
    assert later.due is True
    assert later.follow_up_reason is FollowUpReason.CALLBACK_REQUESTED
    assert later.approved_move is SalesMove.SEND_CONTEXTUAL_FOLLOW_UP


def test_callback_without_datetime_uses_cadence_and_does_not_invent_time() -> None:
    decision = decide_contextual_follow_up(
        _snapshot(
            callback_requested=True,
            objection_deferred=False,
            preferred_contact_at=None,
            last_inbound_at=NOW - timedelta(hours=25),
        ),
        NOW,
    )
    assert decision.due is True
    assert decision.follow_up_reason is FollowUpReason.CALLBACK_REQUESTED


def test_callback_follow_up_does_not_promise_a_staff_call() -> None:
    text = phrase_contextual_follow_up(FollowUpReason.CALLBACK_REQUESTED).casefold()
    assert "following up as you asked" in text
    assert "team member" not in text
    assert "call you" not in text


def test_quiet_hours_delay_send() -> None:
    quiet_now = datetime(2026, 9, 8, 2, 0, tzinfo=timezone.utc)
    decision = decide_contextual_follow_up(
        _snapshot(
            last_inbound_at=quiet_now - timedelta(hours=25),
            timezone_name="UTC",
            quiet_hours=("20:00", "08:00"),
        ),
        quiet_now,
    )
    assert decision.due is False
    assert decision.skip_code == "quiet_hours"


def test_human_takeover_and_terminal_states_are_not_due() -> None:
    takeover = decide_contextual_follow_up(_snapshot(human_owns=True), NOW)
    assert takeover.skip_code == "human_takeover"
    booked = decide_contextual_follow_up(
        _snapshot(process_state=ProcessState.BOOKED),
        NOW,
    )
    assert booked.skip_code == "case_not_eligible"
    commercial_follow_up = decide_contextual_follow_up(
        _snapshot(process_state=ProcessState.FOLLOW_UP),
        NOW,
    )
    assert commercial_follow_up.skip_code == "case_not_eligible"


def test_qualified_without_booking_is_not_treated_as_booking_not_completed() -> None:
    decision = decide_contextual_follow_up(
        _snapshot(
            process_state=ProcessState.QUALIFIED,
            objection_deferred=False,
            callback_requested=False,
        ),
        NOW,
    )
    assert decision.due is False
    assert decision.follow_up_reason is None
    assert decision.skip_code == "case_not_eligible"


def test_no_sales_reason_is_not_due() -> None:
    decision = decide_contextual_follow_up(
        _snapshot(callback_requested=False, objection_deferred=False),
        NOW,
    )
    assert decision.skip_code == "no_sales_follow_up_reason"


def test_this_slice_does_not_select_unimplemented_spec_reasons() -> None:
    assert FollowUpReason.CALLBACK_REQUESTED in IMPLEMENTED_REASONS
    assert FollowUpReason.OBJECTION_DEFERRED in IMPLEMENTED_REASONS
    assert FollowUpReason.BOOKING_NOT_COMPLETED not in IMPLEMENTED_REASONS


def test_cadence_defaults_match_spec_when_playbook_is_missing() -> None:
    cadence, maximum, quiet = cadence_from_config(
        None,
        {"communication": {"quiet_hours": {"starts": "21:00", "ends": "08:00"}}},
    )
    assert cadence == (24, 72, 168)
    assert maximum == 3
    assert quiet == ("21:00", "08:00")
    assert timezone_from_sources(None, {"business": {"timezone": "America/Los_Angeles"}}) == (
        "America/Los_Angeles"
    )
