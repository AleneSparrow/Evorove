"""Contextual sales follow-up after a pause (sales-agent spec section 13).

Distinct from stalled-lead SMS in `src/engine/follow_up.py` (form-completeness
nudges for pre-QUALIFIED cases) and from `ProcessState.FOLLOW_UP` (a
post-commercial commercial-workflow state). This module never changes
ProcessState, never qualifies a lead, and never creates a CRM task.

Code selects the reason, due time, and whether sending is allowed. The model
only phrases the already chosen `SEND_CONTEXTUAL_FOLLOW_UP` move.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.domain.sales import (
    FollowUpReason,
    ObjectionStatus,
    SalesMove,
    SalesStage,
)
from src.domain.states import ProcessState


IMPLEMENTED_REASONS = frozenset({
    FollowUpReason.CALLBACK_REQUESTED,
    FollowUpReason.OBJECTION_DEFERRED,
})
ELIGIBLE_PROCESS_STATES = frozenset({
    ProcessState.NEW_LEAD,
    ProcessState.CONTACTED,
    ProcessState.QUALIFYING,
})
DEFAULT_CADENCE_HOURS = (24, 72, 168)
DEFAULT_MAXIMUM_ATTEMPTS = 3
DEFAULT_TIMEZONE = "America/New_York"
# Keep sales delivery-attempt keys out of the stalled-lead 1..N range on
# follow_up_delivery_attempts (same table, different idempotency space).
SALES_FOLLOW_UP_ATTEMPT_BASE = 10_000

_REASON_PHRASES = {
    FollowUpReason.OBJECTION_DEFERRED: (
        "Just checking in — no rush. Whenever you are ready, I can help with the next step."
    ),
    FollowUpReason.CALLBACK_REQUESTED: (
        "Following up as you asked. When you are ready, I can help with the next step."
    ),
}


@dataclass(frozen=True, slots=True)
class ContextualFollowUpSnapshot:
    process_state: ProcessState
    sales_stage: SalesStage
    callback_requested: bool
    objection_deferred: bool
    preferred_contact_at: datetime | None
    last_inbound_at: datetime | None
    last_sales_follow_up_at: datetime | None
    attempts_sent: int
    sms_consent: bool
    has_phone: bool
    sms_suppressed: bool
    human_owns: bool
    timezone_name: str
    quiet_hours: tuple[str, str] | None
    cadence_hours: tuple[int, ...]
    maximum_attempts: int


@dataclass(frozen=True, slots=True)
class ContextualFollowUpDecision:
    due: bool
    sendable: bool
    skip_code: str
    follow_up_reason: FollowUpReason | None = None
    attempt_number: int | None = None
    approved_move: SalesMove | None = None

    @property
    def delivery_attempt_number(self) -> int | None:
        if self.attempt_number is None:
            return None
        return SALES_FOLLOW_UP_ATTEMPT_BASE + self.attempt_number


def decide_contextual_follow_up(
    snapshot: ContextualFollowUpSnapshot,
    now: datetime,
) -> ContextualFollowUpDecision:
    if snapshot.human_owns:
        return _skip("human_takeover")
    if snapshot.process_state not in ELIGIBLE_PROCESS_STATES:
        return _skip("case_not_eligible")

    follow_up_reason = _select_reason(snapshot)
    if follow_up_reason is None:
        return _skip("no_sales_follow_up_reason")

    if not snapshot.sms_consent:
        return _skip("no_sms_consent", follow_up_reason)
    if not snapshot.has_phone:
        return _skip("no_phone", follow_up_reason)
    if snapshot.sms_suppressed:
        return _skip("sms_suppressed", follow_up_reason)

    cadence = snapshot.cadence_hours or DEFAULT_CADENCE_HOURS
    maximum_attempts = snapshot.maximum_attempts or DEFAULT_MAXIMUM_ATTEMPTS
    if snapshot.attempts_sent >= maximum_attempts:
        return _skip("max_attempts_reached", follow_up_reason)
    if snapshot.attempts_sent >= len(cadence):
        return _skip("no_configured_delay_for_this_attempt", follow_up_reason)

    last_activity = _last_activity_at(snapshot)
    if last_activity is None:
        return _skip("no_recorded_activity", follow_up_reason)

    due_at = last_activity + timedelta(hours=cadence[snapshot.attempts_sent])
    if (
        follow_up_reason is FollowUpReason.CALLBACK_REQUESTED
        and snapshot.preferred_contact_at is not None
        and snapshot.attempts_sent == 0
    ):
        due_at = max(due_at, snapshot.preferred_contact_at)
    if now < due_at:
        return _skip("delay_not_elapsed", follow_up_reason)
    if _in_quiet_hours(now, snapshot.timezone_name, snapshot.quiet_hours):
        return _skip("quiet_hours", follow_up_reason)

    attempt_number = snapshot.attempts_sent + 1
    return ContextualFollowUpDecision(
        due=True,
        sendable=True,
        skip_code="due",
        follow_up_reason=follow_up_reason,
        attempt_number=attempt_number,
        approved_move=SalesMove.SEND_CONTEXTUAL_FOLLOW_UP,
    )


def phrase_contextual_follow_up(reason: FollowUpReason) -> str:
    return _REASON_PHRASES.get(
        reason,
        "I can follow up with the next step when you are ready.",
    )


def cadence_from_config(
    playbook: Mapping[str, object] | None,
    business_dna: Mapping[str, object],
) -> tuple[tuple[int, ...], int, tuple[str, str] | None]:
    follow_up = _mapping(playbook, "follow_up") if playbook is not None else None
    cadence = _positive_int_sequence(
        None if follow_up is None else follow_up.get("cadence_hours")
    )
    if not cadence:
        cadence = DEFAULT_CADENCE_HOURS
    maximum = follow_up.get("maximum_attempts") if follow_up is not None else None
    maximum_attempts = (
        maximum if isinstance(maximum, int) and maximum > 0 else DEFAULT_MAXIMUM_ATTEMPTS
    )
    quiet = _quiet_hours_from(follow_up) if follow_up is not None else None
    if quiet is None:
        quiet = _quiet_hours_from(_mapping(business_dna, "communication"))
    return cadence, maximum_attempts, quiet


def timezone_from_sources(
    customer_timezone: str | None,
    business_dna: Mapping[str, object],
) -> str:
    if isinstance(customer_timezone, str) and customer_timezone.strip():
        try:
            ZoneInfo(customer_timezone.strip())
            return customer_timezone.strip()
        except ZoneInfoNotFoundError:
            pass
    for section_name in ("business", "booking"):
        section = business_dna.get(section_name)
        if not isinstance(section, Mapping):
            continue
        value = section.get("timezone")
        if isinstance(value, str) and value.strip():
            try:
                ZoneInfo(value.strip())
                return value.strip()
            except ZoneInfoNotFoundError:
                continue
    return DEFAULT_TIMEZONE


def _select_reason(snapshot: ContextualFollowUpSnapshot) -> FollowUpReason | None:
    if snapshot.callback_requested:
        return FollowUpReason.CALLBACK_REQUESTED
    if snapshot.objection_deferred:
        return FollowUpReason.OBJECTION_DEFERRED
    return None


def _last_activity_at(snapshot: ContextualFollowUpSnapshot) -> datetime | None:
    timestamps = [
        value
        for value in (snapshot.last_inbound_at, snapshot.last_sales_follow_up_at)
        if value is not None
    ]
    return max(timestamps) if timestamps else None


def _in_quiet_hours(
    now: datetime,
    timezone_name: str,
    quiet_hours: tuple[str, str] | None,
) -> bool:
    if quiet_hours is None:
        return False
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    starts = _parse_hhmm(quiet_hours[0])
    ends = _parse_hhmm(quiet_hours[1])
    if starts is None or ends is None:
        return False
    local = now.astimezone(zone).time()
    if starts <= ends:
        return starts <= local < ends
    return local >= starts or local < ends


def _parse_hhmm(value: str) -> time | None:
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour, minute)


def _quiet_hours_from(section: Mapping[str, object] | None) -> tuple[str, str] | None:
    if section is None:
        return None
    raw = section.get("quiet_hours")
    if isinstance(raw, Mapping):
        starts = raw.get("starts")
        ends = raw.get("ends")
        if isinstance(starts, str) and isinstance(ends, str):
            return starts, ends
        return None
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        starts, ends = raw
        if isinstance(starts, str) and isinstance(ends, str):
            return starts, ends
    return None


def _positive_int_sequence(value: object) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        return ()
    if not all(isinstance(item, int) and item > 0 for item in value):
        return ()
    return tuple(value)


def _mapping(source: Mapping[str, object], key: str) -> Mapping[str, object] | None:
    value = source.get(key)
    return value if isinstance(value, Mapping) else None


def _skip(
    code: str,
    follow_up_reason: FollowUpReason | None = None,
) -> ContextualFollowUpDecision:
    return ContextualFollowUpDecision(
        due=False,
        sendable=False,
        skip_code=code,
        follow_up_reason=follow_up_reason,
    )


def objection_is_deferred(status: ObjectionStatus | None) -> bool:
    return status is ObjectionStatus.DEFERRED
