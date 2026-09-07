from datetime import datetime, timezone

import pytest

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
from src.engine.sales_policy import (
    InvalidSalesStageTransition,
    SalesPolicyEngine,
    SalesStageMachine,
)


def _profile(**overrides: object) -> CustomerSalesProfile:
    values = {
        "business_id": "biz-1",
        "case_id": "case-1",
        "stage": SalesStage.DISCOVERY,
    }
    values.update(overrides)
    return CustomerSalesProfile(**values)  # type: ignore[arg-type]


def _analysis(**overrides: object) -> SalesTurnAnalysis:
    values = {"observed_stage": SalesStage.DISCOVERY, "confidence": 0.9}
    values.update(overrides)
    return SalesTurnAnalysis(**values)  # type: ignore[arg-type]


def _objection(
    *,
    status: ObjectionStatus,
    cause: str | None = None,
    objection_type: ObjectionType = ObjectionType.PRICE,
) -> SalesObjection:
    return SalesObjection(
        objection_type=objection_type,
        status=status,
        evidence=CustomerEvidence("message-1", "That is more than I expected"),
        cause=cause,
    )


def test_sales_stage_machine_is_separate_and_closed() -> None:
    machine = SalesStageMachine()
    machine.validate(SalesStage.GREETING, SalesStage.DISCOVERY)
    machine.validate(SalesStage.OBJECTION_HANDLING, SalesStage.BOOKING)
    with pytest.raises(InvalidSalesStageTransition, match="GREETING to WON"):
        machine.validate(SalesStage.GREETING, SalesStage.WON)
    with pytest.raises(ValueError, match="every SalesStage"):
        SalesStageMachine({SalesStage.GREETING: frozenset({SalesStage.DISCOVERY})})


def test_human_review_has_highest_policy_precedence() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(current_problem="missed leads", desired_outcome="book more calls"),
        _analysis(requires_human=True, commitment_level=CommitmentLevel.READY_FOR_NEXT_STEP),
        approved_knowledge_available=True,
        booking_available=True,
    )
    assert decision.move is SalesMove.HANDOFF_TO_HUMAN
    assert decision.requires_human


def test_new_objection_is_diagnosed_before_any_commitment() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(current_problem="missed leads", desired_outcome="book more calls"),
        _analysis(
            objections=(_objection(status=ObjectionStatus.ACTIVE),),
            commitment_level=CommitmentLevel.READY_FOR_NEXT_STEP,
        ),
        approved_knowledge_available=True,
        booking_available=True,
    )
    assert decision.move is SalesMove.DIAGNOSE_OBJECTION
    assert decision.target_stage is SalesStage.OBJECTION_HANDLING


def test_diagnosed_objection_is_answered_from_business_facts_without_cards() -> None:
    analysis = _analysis(objections=(_objection(status=ObjectionStatus.DIAGNOSED, cause="value"),))
    without_grounding = SalesPolicyEngine().decide(_profile(), analysis)
    with_facts = SalesPolicyEngine().decide(
        _profile(), analysis, business_facts_available=True,
    )
    with_knowledge = SalesPolicyEngine().decide(
        _profile(), analysis, approved_knowledge_available=True,
    )
    assert without_grounding.move is SalesMove.REQUEST_BUSINESS_FACT
    assert without_grounding.target_stage is SalesStage.FOLLOW_UP
    assert not without_grounding.requires_human
    assert with_facts.move is SalesMove.ANSWER_OBJECTION
    assert not with_facts.knowledge_required
    assert with_knowledge.move is SalesMove.ANSWER_OBJECTION
    assert with_knowledge.knowledge_required


def test_diagnosed_other_objection_is_answered_from_business_facts() -> None:
    analysis = _analysis(
        objections=(_objection(
            status=ObjectionStatus.DIAGNOSED,
            cause="stated_concern",
            objection_type=ObjectionType.OTHER,
        ),),
    )
    decision = SalesPolicyEngine().decide(
        _profile(), analysis, business_facts_available=True,
    )
    assert decision.move is SalesMove.ANSWER_OBJECTION
    assert not decision.requires_human
    assert not decision.knowledge_required


def test_addressed_objection_must_be_checked_not_assumed_resolved() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(),
        _analysis(objections=(_objection(status=ObjectionStatus.ADDRESSED, cause="value"),)),
        approved_knowledge_available=True,
    )
    assert decision.move is SalesMove.CHECK_OBJECTION_RESOLUTION


def test_missing_discovery_context_asks_a_question() -> None:
    decision = SalesPolicyEngine().decide(_profile(current_problem="missed leads"), _analysis())
    assert decision.move is SalesMove.ASK_DISCOVERY_QUESTION
    assert decision.target_stage is SalesStage.DISCOVERY


def test_explicit_callback_request_precedes_discovery() -> None:
    callback_at = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    decision = SalesPolicyEngine().decide(
        _profile(),
        _analysis(requested_callback_at=callback_at),
    )
    assert decision.move is SalesMove.SCHEDULE_CALLBACK
    assert decision.target_stage is SalesStage.FOLLOW_UP


def test_preferred_contact_time_signal_schedules_callback_without_datetime() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(),
        _analysis(
            signals=(SalesSignal(
                "preferred_contact_time",
                "tomorrow around 3pm",
                CustomerEvidence("message-1", "call me tomorrow around 3pm"),
            ),),
        ),
    )
    assert decision.move is SalesMove.SCHEDULE_CALLBACK
    assert decision.target_stage is SalesStage.FOLLOW_UP


def test_recommended_callback_move_does_not_authorize_without_evidence() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(),
        _analysis(recommended_moves=(SalesMove.SCHEDULE_CALLBACK,)),
    )
    assert decision.move is not SalesMove.SCHEDULE_CALLBACK


def test_active_objection_precedes_callback_request() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(),
        _analysis(
            objections=(_objection(status=ObjectionStatus.ACTIVE),),
            requested_callback_at=datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc),
        ),
        business_facts_available=True,
    )
    assert decision.move is SalesMove.DIAGNOSE_OBJECTION


def test_ready_customer_gets_slots_only_when_booking_is_available() -> None:
    profile = _profile(
        stage=SalesStage.COMMITMENT,
        current_problem="missed leads",
        desired_outcome="book more calls",
    )
    analysis = _analysis(commitment_level=CommitmentLevel.READY_FOR_NEXT_STEP)
    unavailable = SalesPolicyEngine().decide(profile, analysis, booking_available=False)
    available = SalesPolicyEngine().decide(profile, analysis, booking_available=True)
    assert unavailable.move is SalesMove.ASK_FOR_COMMITMENT
    assert available.move is SalesMove.OFFER_BOOKING_SLOTS


def test_confirmed_need_presents_from_business_facts_without_knowledge_cards() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(
            stage=SalesStage.NEEDS_CONFIRMED,
            current_problem="AC stopped cooling",
            desired_outcome="it working this week",
        ),
        _analysis(),
        business_facts_available=True,
    )
    assert decision.move is SalesMove.PRESENT_RELEVANT_VALUE
    assert decision.target_stage is SalesStage.PRESENTATION
    assert not decision.knowledge_required
    assert not decision.requires_human


def test_presentation_asks_for_commitment_instead_of_repeating_value() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(
            stage=SalesStage.PRESENTATION,
            current_problem="AC stopped cooling",
            desired_outcome="it working this week",
        ),
        _analysis(),
        business_facts_available=True,
    )
    assert decision.move is SalesMove.ASK_FOR_COMMITMENT
    assert decision.target_stage is SalesStage.COMMITMENT


def test_operational_gaps_are_asked_in_discovery_not_as_qualification_stage() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(
            current_problem="AC stopped cooling",
            desired_outcome="it working this week",
        ),
        _analysis(commitment_level=CommitmentLevel.READY_FOR_NEXT_STEP),
        business_facts_available=True,
        booking_available=True,
        operational_intake_incomplete=True,
    )
    assert decision.move is SalesMove.ASK_DISCOVERY_QUESTION
    assert decision.target_stage is SalesStage.DISCOVERY


def test_deferred_need_to_think_nurtures_instead_of_asking_commitment() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(
            stage=SalesStage.OBJECTION_HANDLING,
            current_problem="AC stopped cooling",
            desired_outcome="it working this week",
        ),
        _analysis(objections=(_objection(status=ObjectionStatus.DEFERRED),)),
        business_facts_available=True,
        booking_available=True,
    )
    assert decision.move is SalesMove.NURTURE_WITHOUT_PRESSURE
    assert decision.target_stage is SalesStage.FOLLOW_UP
    assert not decision.requires_human


def test_deferred_objection_still_books_on_explicit_ready() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(
            stage=SalesStage.FOLLOW_UP,
            current_problem="AC stopped cooling",
            desired_outcome="it working this week",
        ),
        _analysis(
            objections=(_objection(status=ObjectionStatus.DEFERRED),),
            commitment_level=CommitmentLevel.READY_FOR_NEXT_STEP,
        ),
        business_facts_available=True,
        booking_available=True,
    )
    assert decision.move is SalesMove.OFFER_BOOKING_SLOTS
    assert decision.target_stage is SalesStage.BOOKING


def test_confirmed_need_without_facts_asks_the_business_not_a_person() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(
            stage=SalesStage.NEEDS_CONFIRMED,
            current_problem="AC stopped cooling",
            desired_outcome="it working this week",
        ),
        _analysis(),
    )
    assert decision.move is SalesMove.REQUEST_BUSINESS_FACT
    assert decision.target_stage is SalesStage.FOLLOW_UP
    assert not decision.requires_human


def test_pending_owner_fact_keeps_requesting_until_the_fact_arrives() -> None:
    decision = SalesPolicyEngine().decide(
        _profile(
            stage=SalesStage.FOLLOW_UP,
            current_problem="AC stopped cooling",
            desired_outcome="it working this week",
            last_move=SalesMove.REQUEST_BUSINESS_FACT,
            metadata={
                "pending_business_fact_request": {
                    "needed_for": "presentation",
                    "reason_code": "approved_presentation_knowledge_missing",
                    "requested_at": "2026-09-07T12:00:00+00:00",
                    "resume_stage": "NEEDS_CONFIRMED",
                }
            },
        ),
        _analysis(observed_stage=SalesStage.FOLLOW_UP),
    )
    assert decision.move is SalesMove.REQUEST_BUSINESS_FACT
    assert not decision.requires_human

