"""Live sales-turn helpers: evidence-only profile merge and safe wording.

The conversational reply is chosen by SalesPolicyEngine. Qualification and
ProcessEngine stay out of "what to say" unless the sale has reached a
commitment, a loss, or a human handoff.
"""

from dataclasses import dataclass, replace
from typing import Any, Mapping
import re

from src.domain.qualification import QualificationReasonCode, QualificationResult
from src.domain.sales import (
    CommitmentLevel,
    CustomerEvidence,
    CustomerSalesProfile,
    ObjectionStatus,
    ObjectionType,
    SalesMove,
    SalesObjection,
    SalesSignal,
    SalesStage,
    SalesTurnAnalysis,
)
from src.engine.sales_objections import (
    detect_objection_type,
    infer_objection_cause,
    looks_like_deferral,
    looks_like_resolution,
    stated_concern_excerpt,
)
from src.engine.sales_owner_facts import owner_listed_facts


_SAFE_DISCOVERY_FALLBACK = (
    "Thanks for sharing that. What problem are you trying to solve, "
    "and what would a good outcome look like?"
)
_MOVE_PHRASES: dict[SalesMove, str] = {
    SalesMove.GREET_AND_SET_CONTEXT: (
        "Thanks for reaching out. What are you hoping to get help with?"
    ),
    SalesMove.ASK_DISCOVERY_QUESTION: (
        "What problem are you trying to solve, and what would a good outcome look like?"
    ),
    SalesMove.REFLECT_CUSTOMER_NEED: (
        "It sounds like that is what you want help with. Did I understand that correctly?"
    ),
    SalesMove.CONFIRM_CUSTOMER_NEED: (
        "Just to make sure I have this right — is that the main thing you want help with?"
    ),
    SalesMove.PRESENT_RELEVANT_VALUE: (
        "We can help with that. This is the kind of request the business is set up to handle."
    ),
    SalesMove.ASK_FOR_COMMITMENT: (
        "When you are ready, would you like to take the next step?"
    ),
    SalesMove.NURTURE_WITHOUT_PRESSURE: (
        "No rush. I can follow up when the timing is better."
    ),
    SalesMove.REQUEST_BUSINESS_FACT: (
        "I need to confirm one detail with the business before I can answer "
        "that honestly. I'll follow up here as soon as I have it."
    ),
    SalesMove.SEND_CONTEXTUAL_FOLLOW_UP: (
        "I can follow up with the next step when you are ready."
    ),
    SalesMove.SCHEDULE_CALLBACK: (
        "I'll follow up with you at the time you asked for."
    ),
    SalesMove.END_CONTACT: (
        "Understood. I will not continue this conversation."
    ),
    SalesMove.DIAGNOSE_OBJECTION: (
        "I hear that concern. What about it feels like the main issue?"
    ),
    SalesMove.ANSWER_OBJECTION: (
        "I hear that concern. We can look at the actual next step for what you said you need."
    ),
    SalesMove.CHECK_OBJECTION_RESOLUTION: (
        "Does that address the concern, or is something still in the way?"
    ),
}
_PROBLEM_PATTERNS = (
    re.compile(
        r"(?:my|the)\s+[^.]{1,60}?\s+(?:stopped|is broken|broke|isn't working|"
        r"is not working|won't \w+|leaking|missed)",
        re.IGNORECASE,
    ),
    re.compile(
        r"i need someone to look at [^.]{1,60}",
        re.IGNORECASE,
    ),
    re.compile(
        r"i need help with [^.]{1,60}",
        re.IGNORECASE,
    ),
)
_OUTCOME_PATTERNS = (
    re.compile(
        r"i need (?:it |them )?(?:working|fixed|running|resolved)[^.]{0,40}",
        re.IGNORECASE,
    ),
    re.compile(
        r"so (?:i|we) can [^.]{1,60}",
        re.IGNORECASE,
    ),
    re.compile(
        r"looking to (?:get|have) [^.]{1,40}",
        re.IGNORECASE,
    ),
)
_READY_PATTERN = re.compile(
    r"\b(?:i(?:'m| am) ready|let'?s (?:do it|book|go)|book(?: me)?|"
    r"schedule(?: it)?|sign me up|yes[,.]? (?:book|please|let'?s))\b",
    re.IGNORECASE,
)
_ZIP_ONLY = re.compile(r"^\s*\d{5}(?:-\d{4})?\s*$")
_COMMITMENT_STAGES = frozenset({
    SalesStage.PRESENTATION,
    SalesStage.OBJECTION_HANDLING,
    SalesStage.COMMITMENT,
    SalesStage.BOOKING,
    SalesStage.FOLLOW_UP,
})
_LOW_CONFIDENCE = frozenset({QualificationReasonCode.LOW_CONFIDENCE.value})
_CALLBACK_PATTERNS = (
    re.compile(r"\b(?:can you |could you |please )?call me(?: back)?\b", re.IGNORECASE),
    re.compile(r"\bgive me a call\b", re.IGNORECASE),
    re.compile(r"\b(?:phone|ring) me\b", re.IGNORECASE),
    re.compile(r"\bschedule a (?:call|callback)\b", re.IGNORECASE),
    re.compile(r"\bhave someone call(?: me)?\b", re.IGNORECASE),
    re.compile(r"\bcallback\b", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class DeterministicSalesTurnAnalyzer:
    """Evidence-grounded fallback. Does not treat zip or a service label as a sale."""

    def analyze(
        self,
        *,
        source_message_id: str,
        customer_message: str,
        profile_context: Mapping[str, Any],
        conversation_context: Mapping[str, Any],
    ) -> SalesTurnAnalysis:
        del conversation_context
        stage_value = profile_context.get("sales_stage")
        try:
            observed = SalesStage(stage_value) if isinstance(stage_value, str) else SalesStage.DISCOVERY
        except ValueError:
            observed = SalesStage.DISCOVERY
        if _ZIP_ONLY.match(customer_message or ""):
            return SalesTurnAnalysis(observed_stage=observed, confidence=1.0)
        signals: list[SalesSignal] = []
        if not profile_context.get("current_problem"):
            problem = _first_match(_PROBLEM_PATTERNS, customer_message)
            if problem is not None:
                signals.append(SalesSignal(
                    "current_problem", problem, CustomerEvidence(source_message_id, problem),
                ))
        if not profile_context.get("desired_outcome"):
            outcome = _first_match(_OUTCOME_PATTERNS, customer_message)
            if outcome is not None:
                signals.append(SalesSignal(
                    "desired_outcome", outcome, CustomerEvidence(source_message_id, outcome),
                ))
        objections = _objections_from_message(
            source_message_id, customer_message, profile_context,
        )
        if objections:
            observed = SalesStage.OBJECTION_HANDLING
        callback = _callback_from_message(source_message_id, customer_message)
        if callback is not None:
            signals.append(callback)
        ready = (
            observed in _COMMITMENT_STAGES
            and _READY_PATTERN.search(customer_message or "") is not None
        )
        if objections and objections[0].status is not ObjectionStatus.RESOLVED:
            ready = False
        return SalesTurnAnalysis(
            observed_stage=observed,
            confidence=1.0,
            signals=tuple(signals),
            objections=objections,
            recommended_moves=(
                (SalesMove.SCHEDULE_CALLBACK,) if callback is not None else ()
            ),
            commitment_level=(
                CommitmentLevel.READY_FOR_NEXT_STEP if ready else CommitmentLevel.UNKNOWN
            ),
        )


def _objections_from_message(
    source_message_id: str,
    customer_message: str,
    profile_context: Mapping[str, Any],
) -> tuple[SalesObjection, ...]:
    status_value = profile_context.get("active_objection_status")
    type_value = profile_context.get("active_objection_type")
    try:
        active_status = ObjectionStatus(status_value) if isinstance(status_value, str) else None
    except ValueError:
        active_status = None
    try:
        active_type = ObjectionType(type_value) if isinstance(type_value, str) else None
    except ValueError:
        active_type = None
    prior_cause = profile_context.get("active_objection_cause")
    if not isinstance(prior_cause, str) or not prior_cause.strip():
        prior_cause = None

    detected = detect_objection_type(customer_message)
    if active_status is ObjectionStatus.ADDRESSED and looks_like_resolution(customer_message):
        resolution_excerpt = (detected[1] if detected else customer_message.strip()[:80]) or "yes"
        if active_type is not None:
            return (SalesObjection(
                active_type,
                ObjectionStatus.RESOLVED,
                CustomerEvidence(source_message_id, resolution_excerpt),
                prior_cause,
            ),)

    if (
        active_type in {ObjectionType.NEED_TO_THINK, ObjectionType.TIMING}
        and active_status in {
            ObjectionStatus.ACTIVE, ObjectionStatus.DIAGNOSED, ObjectionStatus.ADDRESSED,
        }
        and looks_like_deferral(customer_message)
    ):
        excerpt = (detected[1] if detected else customer_message.strip()[:80]) or "later"
        return (SalesObjection(
            active_type,
            ObjectionStatus.DEFERRED,
            CustomerEvidence(source_message_id, excerpt),
        ),)

    if active_type is not None and active_status in {
        ObjectionStatus.ACTIVE, ObjectionStatus.DIAGNOSED,
    } and prior_cause is None:
        remapped = detect_objection_type(customer_message)
        use_type = remapped[0] if remapped is not None else active_type
        inferred = infer_objection_cause(use_type, customer_message)
        if (
            inferred is None
            and use_type is ObjectionType.OTHER
            and _READY_PATTERN.search(customer_message or "") is None
        ):
            excerpt = stated_concern_excerpt(customer_message)
            if excerpt is not None:
                inferred = ("stated_concern", excerpt)
        if inferred is not None:
            cause, excerpt = inferred
            deferred = (
                use_type is ObjectionType.NEED_TO_THINK and cause == "need_time"
            )
            return (SalesObjection(
                use_type,
                ObjectionStatus.DEFERRED if deferred else ObjectionStatus.DIAGNOSED,
                CustomerEvidence(source_message_id, excerpt),
                None if deferred else cause,
            ),)

    if detected is None:
        return ()
    objection_type, excerpt = detected
    return (SalesObjection(
        objection_type,
        ObjectionStatus.ACTIVE,
        CustomerEvidence(source_message_id, excerpt),
    ),)


def merge_profile_from_analysis(
    profile: CustomerSalesProfile,
    analysis: SalesTurnAnalysis,
) -> CustomerSalesProfile:
    """Apply only evidence-bearing signals. Completeness of zip/service is ignored."""

    values: dict[str, Any] = {}
    criteria = list(profile.decision_criteria)
    metadata = dict(profile.metadata)
    for signal in analysis.signals:
        if signal.kind in {"customer_goal", "current_problem", "desired_outcome"}:
            values[signal.kind] = signal.value
        elif signal.kind == "decision_criteria" and signal.value not in criteria:
            criteria.append(signal.value)
        elif signal.kind == "preferred_channel":
            values["preferred_channel"] = signal.value
        elif signal.kind == "preferred_contact_time":
            metadata["preferred_contact_time"] = signal.value
            metadata["callback_status"] = "requested"
    values["decision_criteria"] = tuple(criteria)
    values["commitment_level"] = analysis.commitment_level
    if analysis.objections:
        values["active_objection"] = analysis.objections[0]
    if analysis.requested_callback_at is not None:
        values["preferred_contact_at"] = analysis.requested_callback_at
        metadata["callback_status"] = "requested"
    if metadata != dict(profile.metadata):
        values["metadata"] = metadata
    return replace(profile, **values)


def operationally_qualified_for_commitment(qualification: QualificationResult) -> bool:
    """A shaky reading of an already-complete case is not an incomplete sale."""

    if qualification.qualified:
        return True
    if set(qualification.reason_codes) != _LOW_CONFIDENCE:
        return False
    return (
        not qualification.missing_fields
        and not qualification.unanswered_questions
        and qualification.service_id is not None
    )


def booking_available_for_live_turn(
    qualification: QualificationResult,
    profile: CustomerSalesProfile,
    analysis: SalesTurnAnalysis,
) -> bool:
    """Commercial next step requires operational fit, a late sales stage, and an explicit ready signal."""

    if not operationally_qualified_for_commitment(qualification):
        return False
    if analysis.commitment_level is not CommitmentLevel.READY_FOR_NEXT_STEP:
        return False
    return profile.stage in _COMMITMENT_STAGES


def discovery_prompt(
    profile: CustomerSalesProfile,
    qualification: QualificationResult,
    dna: Mapping[str, Any],
) -> str:
    if not profile.current_problem:
        return "What problem are you trying to solve right now?"
    if not profile.desired_outcome:
        return "What would a good outcome look like?"
    questions = dna.get("customer_information", {})
    field_questions = questions.get("field_questions", {}) if isinstance(questions, Mapping) else {}
    if isinstance(field_questions, Mapping):
        for field in qualification.missing_fields:
            prompt = field_questions.get(field)
            if isinstance(prompt, str) and prompt.strip():
                return prompt.strip()
    if qualification.unanswered_questions:
        return qualification.unanswered_questions[0]
    return _MOVE_PHRASES[SalesMove.ASK_DISCOVERY_QUESTION]


def listed_business_facts(
    dna: Mapping[str, Any], service_id: str | None,
) -> tuple[tuple[str, str], ...]:
    """Name and description only. Catalog prices are not passed as claimable facts."""

    facts: list[tuple[str, str]] = []
    business = dna.get("business", {})
    if isinstance(business, Mapping):
        for key in ("name", "description"):
            value = business.get(key)
            if isinstance(value, str) and value.strip():
                facts.append((f"business.{key}", value.strip()))
    if not service_id:
        return tuple(facts)
    for service in dna.get("services", []):
        if not isinstance(service, Mapping) or str(service.get("id")) != service_id:
            continue
        for key in ("name", "description"):
            value = service.get(key)
            if isinstance(value, str) and value.strip():
                facts.append((f"service.{key}", value.strip()))
        break
    return tuple(facts)


def combined_business_facts(
    dna: Mapping[str, Any],
    service_id: str | None,
    profile: CustomerSalesProfile | None = None,
) -> tuple[tuple[str, str], ...]:
    facts = listed_business_facts(dna, service_id)
    if profile is None:
        return facts
    return facts + owner_listed_facts(profile)


def business_facts_available(
    dna: Mapping[str, Any],
    service_id: str | None,
    profile: CustomerSalesProfile | None = None,
) -> bool:
    return bool(combined_business_facts(dna, service_id, profile))


def phrase_approved_move(move: SalesMove, *, safe_fallback: str) -> str:
    if move is SalesMove.HANDOFF_TO_HUMAN:
        return safe_fallback
    return _MOVE_PHRASES.get(move, _SAFE_DISCOVERY_FALLBACK)


def _callback_from_message(source_message_id: str, customer_message: str) -> SalesSignal | None:
    excerpt = _first_match(_CALLBACK_PATTERNS, customer_message)
    if excerpt is None:
        return None
    return SalesSignal(
        "preferred_contact_time",
        excerpt,
        CustomerEvidence(source_message_id, excerpt),
    )


def _first_match(patterns: tuple[re.Pattern[str], ...], text: str) -> str | None:
    for pattern in patterns:
        matched = pattern.search(text or "")
        if matched is not None:
            excerpt = matched.group(0).strip()
            if excerpt:
                return excerpt
    return None
