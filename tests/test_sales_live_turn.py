from datetime import datetime, timezone

from src.domain.qualification import QualificationReasonCode, QualificationResult
from src.domain.sales import (
    CommitmentLevel,
    CustomerEvidence,
    CustomerSalesProfile,
    ObjectionStatus,
    ObjectionType,
    SalesKnowledgeCard,
    SalesKnowledgeStatus,
    SalesMove,
    SalesObjection,
    SalesSignal,
    SalesStage,
    SalesTurnAnalysis,
)
from src.domain.states import ProcessState
from src.engine.sales_live_turn import (
    DeterministicSalesTurnAnalyzer,
    booking_available_for_live_turn,
    merge_profile_from_analysis,
    phrase_approved_move,
)
from src.engine.sales_objections import matching_knowledge
from src.engine.sales_policy import SalesPolicyEngine

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def _profile(**overrides: object) -> CustomerSalesProfile:
    values = {
        "business_id": "biz-1",
        "case_id": "case-1",
        "stage": SalesStage.DISCOVERY,
    }
    values.update(overrides)
    return CustomerSalesProfile(**values)  # type: ignore[arg-type]


def _qualification(*, qualified: bool = True, booking_allowed: bool = True) -> QualificationResult:
    if qualified:
        return QualificationResult(
            qualified=True,
            reasons=("All mandatory qualification requirements are satisfied",),
            reason_codes=(QualificationReasonCode.QUALIFIED.value,),
            missing_fields=(),
            unanswered_questions=(),
            confidence=0.95,
            recommended_next_state=ProcessState.QUALIFIED,
            requires_human=False,
            booking_allowed=booking_allowed,
            service_id="diagnostic-visit",
        )
    return QualificationResult(
        qualified=False,
        reasons=("Additional customer information is required",),
        reason_codes=(QualificationReasonCode.MISSING_INFORMATION.value,),
        missing_fields=("service_address",),
        unanswered_questions=(),
        confidence=0.95,
        recommended_next_state=ProcessState.QUALIFYING,
        requires_human=False,
        booking_allowed=False,
        service_id="diagnostic-visit",
    )


def test_deterministic_analyzer_does_not_invent_discovery_from_service_and_zip() -> None:
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-1",
        customer_message="AC diagnostic in 60601",
        profile_context={"sales_stage": "GREETING"},
        conversation_context={},
    )
    assert analysis.signals == ()
    assert analysis.objections == ()
    assert analysis.commitment_level is CommitmentLevel.UNKNOWN


def test_deterministic_analyzer_extracts_problem_and_outcome_with_verbatim_evidence() -> None:
    message = "My AC stopped cooling and I need it working this week."
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-2",
        customer_message=message,
        profile_context={"sales_stage": "DISCOVERY"},
        conversation_context={},
    )
    kinds = {item.kind: item for item in analysis.signals}
    assert "current_problem" in kinds
    assert kinds["current_problem"].evidence.excerpt in message
    assert "desired_outcome" in kinds
    assert kinds["desired_outcome"].evidence.excerpt in message
    assert analysis.commitment_level is CommitmentLevel.UNKNOWN


def test_bare_yes_is_not_a_booking_signal_during_discovery() -> None:
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-3",
        customer_message="Yes, book me",
        profile_context={"sales_stage": "DISCOVERY"},
        conversation_context={},
    )
    assert analysis.commitment_level is CommitmentLevel.UNKNOWN


def test_explicit_book_signal_is_ready_only_after_presentation() -> None:
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-4",
        customer_message="Yes, book me",
        profile_context={"sales_stage": "COMMITMENT"},
        conversation_context={},
    )
    assert analysis.commitment_level is CommitmentLevel.READY_FOR_NEXT_STEP


def test_complete_fields_without_commitment_cannot_offer_slots() -> None:
    profile = _profile(stage=SalesStage.DISCOVERY)
    analysis = SalesTurnAnalysis(observed_stage=SalesStage.DISCOVERY, confidence=1.0)
    assert booking_available_for_live_turn(_qualification(), profile, analysis) is False
    decision = SalesPolicyEngine().decide(
        profile, analysis, booking_available=False, approved_knowledge_available=False,
    )
    assert decision.move is SalesMove.ASK_DISCOVERY_QUESTION
    assert decision.target_stage is SalesStage.DISCOVERY


def test_slots_require_commitment_stage_and_explicit_ready_signal() -> None:
    profile = _profile(
        stage=SalesStage.COMMITMENT,
        current_problem="missed calls",
        desired_outcome="book more jobs",
    )
    ready = SalesTurnAnalysis(
        observed_stage=SalesStage.COMMITMENT,
        confidence=0.9,
        commitment_level=CommitmentLevel.READY_FOR_NEXT_STEP,
    )
    assert booking_available_for_live_turn(_qualification(), profile, ready) is True
    assert booking_available_for_live_turn(
        _qualification(qualified=False), profile, ready,
    ) is False
    assert booking_available_for_live_turn(
        _qualification(), _profile(stage=SalesStage.DISCOVERY), ready,
    ) is False


def test_low_confidence_complete_case_can_offer_slots_when_ready() -> None:
    profile = _profile(
        stage=SalesStage.COMMITMENT,
        current_problem="missed calls",
        desired_outcome="book more jobs",
    )
    ready = SalesTurnAnalysis(
        observed_stage=SalesStage.COMMITMENT,
        confidence=0.9,
        commitment_level=CommitmentLevel.READY_FOR_NEXT_STEP,
    )
    shaky = QualificationResult(
        qualified=False,
        reasons=("Intent confidence is below policy or extraction requested review",),
        reason_codes=(QualificationReasonCode.LOW_CONFIDENCE.value,),
        missing_fields=(),
        unanswered_questions=(),
        confidence=0.6,
        recommended_next_state=ProcessState.NEEDS_HUMAN,
        requires_human=True,
        booking_allowed=False,
        service_id="diagnostic-visit",
    )
    incomplete = QualificationResult(
        qualified=False,
        reasons=("Intent confidence is below policy or extraction requested review",),
        reason_codes=(QualificationReasonCode.LOW_CONFIDENCE.value,),
        missing_fields=("service_address",),
        unanswered_questions=(),
        confidence=0.6,
        recommended_next_state=ProcessState.NEEDS_HUMAN,
        requires_human=True,
        booking_allowed=False,
        service_id="diagnostic-visit",
    )
    assert booking_available_for_live_turn(shaky, profile, ready) is True
    assert booking_available_for_live_turn(incomplete, profile, ready) is False


def test_profile_merge_is_evidence_grounded() -> None:
    profile = merge_profile_from_analysis(
        _profile(),
        SalesTurnAnalysis(
            observed_stage=SalesStage.DISCOVERY,
            confidence=0.9,
            signals=(SalesSignal(
                "current_problem",
                "missed after-hours calls",
                CustomerEvidence("msg-1", "we miss after-hours calls"),
            ),),
            commitment_level=CommitmentLevel.INTERESTED,
        ),
    )
    assert profile.current_problem == "missed after-hours calls"
    assert profile.desired_outcome is None
    assert profile.commitment_level is CommitmentLevel.INTERESTED


def test_greeting_wording_does_not_offer_booking_or_price() -> None:
    text = phrase_approved_move(
        SalesMove.GREET_AND_SET_CONTEXT, safe_fallback="A team member will follow up with you.",
    )
    lowered = text.casefold()
    assert "appointment" not in lowered
    assert "quote" not in lowered
    assert "slot" not in lowered
    assert "$" not in text


def test_price_objection_is_detected_with_verbatim_evidence() -> None:
    message = "That's way more than I expected to pay"
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-obj-1",
        customer_message=message,
        profile_context={"sales_stage": "PRESENTATION"},
        conversation_context={},
    )
    assert analysis.observed_stage is SalesStage.OBJECTION_HANDLING
    assert analysis.commitment_level is CommitmentLevel.UNKNOWN
    assert len(analysis.objections) == 1
    objection = analysis.objections[0]
    assert objection.objection_type is ObjectionType.PRICE
    assert objection.status is ObjectionStatus.ACTIVE
    assert objection.cause is None
    assert objection.evidence.excerpt in message


def test_price_cause_is_inferred_only_after_diagnosis() -> None:
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-obj-2",
        customer_message="It's whether it will be worth it",
        profile_context={
            "sales_stage": "OBJECTION_HANDLING",
            "active_objection_type": "PRICE",
            "active_objection_status": "ACTIVE",
        },
        conversation_context={},
    )
    assert analysis.objections[0].status is ObjectionStatus.DIAGNOSED
    assert analysis.objections[0].cause == "value"
    assert analysis.objections[0].evidence.excerpt in "It's whether it will be worth it"


def test_other_objection_is_diagnosed_then_answered_without_a_card() -> None:
    message = "I'm just not comfortable with this"
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-other-1",
        customer_message=message,
        profile_context={"sales_stage": "PRESENTATION"},
        conversation_context={},
    )
    assert analysis.observed_stage is SalesStage.OBJECTION_HANDLING
    assert analysis.objections[0].objection_type is ObjectionType.OTHER
    assert analysis.objections[0].status is ObjectionStatus.ACTIVE
    assert analysis.objections[0].cause is None
    assert analysis.objections[0].evidence.excerpt in message
    decision = SalesPolicyEngine().decide(
        _profile(stage=SalesStage.PRESENTATION),
        analysis,
        business_facts_available=True,
    )
    assert decision.move is SalesMove.DIAGNOSE_OBJECTION
    assert not decision.requires_human

    diagnosed = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-other-2",
        customer_message="The whole process feels messy",
        profile_context={
            "sales_stage": "OBJECTION_HANDLING",
            "active_objection_type": "OTHER",
            "active_objection_status": "ACTIVE",
        },
        conversation_context={},
    )
    assert diagnosed.objections[0].status is ObjectionStatus.DIAGNOSED
    assert diagnosed.objections[0].cause == "stated_concern"
    assert diagnosed.objections[0].evidence.excerpt in "The whole process feels messy"
    answered = SalesPolicyEngine().decide(
        _profile(stage=SalesStage.OBJECTION_HANDLING),
        diagnosed,
        business_facts_available=True,
    )
    assert answered.move is SalesMove.ANSWER_OBJECTION
    assert not answered.requires_human
    assert not answered.knowledge_required


def test_addressed_ready_signal_resolves_objection_and_can_book() -> None:
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-obj-3",
        customer_message="Yes, book me",
        profile_context={
            "sales_stage": "OBJECTION_HANDLING",
            "active_objection_type": "PRICE",
            "active_objection_status": "ADDRESSED",
            "active_objection_cause": "value",
        },
        conversation_context={},
    )
    assert analysis.objections[0].status is ObjectionStatus.RESOLVED
    assert analysis.commitment_level is CommitmentLevel.READY_FOR_NEXT_STEP
    profile = _profile(
        stage=SalesStage.OBJECTION_HANDLING,
        current_problem="AC stopped cooling",
        desired_outcome="it working this week",
    )
    assert booking_available_for_live_turn(_qualification(), profile, analysis) is True
    decision = SalesPolicyEngine().decide(profile, analysis, booking_available=True)
    assert decision.move is SalesMove.OFFER_BOOKING_SLOTS
    assert decision.target_stage is SalesStage.BOOKING


def test_price_knowledge_does_not_authorize_a_trust_answer() -> None:
    price_card = SalesKnowledgeCard(
        "objection-price-001",
        "biz-1",
        1,
        SalesKnowledgeStatus.APPROVED,
        {"title": "Evorove sales objection playbook", "location": "PRICE"},
        "Diagnose price without inventing a discount.",
        ("objection_type=PRICE",),
        created_at=NOW,
        reviewed_at=NOW,
        reviewed_by="test",
    )
    trust = SalesObjection(
        ObjectionType.TRUST,
        ObjectionStatus.DIAGNOSED,
        CustomerEvidence("msg-1", "How do I even know this actually works"),
        "proof",
    )
    assert matching_knowledge((price_card,), trust) == ()
    assert matching_knowledge((price_card,), SalesObjection(
        ObjectionType.PRICE,
        ObjectionStatus.DIAGNOSED,
        CustomerEvidence("msg-1", "That's way more than I expected"),
        "value",
    )) == (price_card,)


def test_callback_phrase_is_detected_with_verbatim_evidence() -> None:
    message = "Can you call me tomorrow around 3pm?"
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-cb-1",
        customer_message=message,
        profile_context={"sales_stage": "DISCOVERY"},
        conversation_context={},
    )
    kinds = {item.kind: item for item in analysis.signals}
    assert "preferred_contact_time" in kinds
    assert kinds["preferred_contact_time"].evidence.excerpt in message
    assert analysis.requested_callback_at is None
    assert analysis.recommended_moves == (SalesMove.SCHEDULE_CALLBACK,)
    decision = SalesPolicyEngine().decide(_profile(), analysis)
    assert decision.move is SalesMove.SCHEDULE_CALLBACK
    assert decision.target_stage is SalesStage.FOLLOW_UP


def test_callback_request_merges_onto_profile_without_inventing_a_datetime() -> None:
    profile = merge_profile_from_analysis(
        _profile(),
        SalesTurnAnalysis(
            observed_stage=SalesStage.DISCOVERY,
            confidence=1.0,
            signals=(SalesSignal(
                "preferred_contact_time",
                "call me tomorrow around 3pm",
                CustomerEvidence("msg-cb-2", "call me tomorrow around 3pm"),
            ),),
        ),
    )
    assert profile.preferred_contact_at is None
    assert profile.metadata["preferred_contact_time"] == "call me tomorrow around 3pm"
    assert profile.metadata["callback_status"] == "requested"


def test_need_to_think_time_answer_is_deferred_not_answered() -> None:
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-think-2",
        customer_message="I just need some time",
        profile_context={
            "sales_stage": "OBJECTION_HANDLING",
            "active_objection_type": "NEED_TO_THINK",
            "active_objection_status": "ACTIVE",
        },
        conversation_context={},
    )
    assert analysis.objections[0].objection_type is ObjectionType.NEED_TO_THINK
    assert analysis.objections[0].status is ObjectionStatus.DEFERRED
    assert analysis.objections[0].cause is None
    profile = _profile(
        stage=SalesStage.OBJECTION_HANDLING,
        current_problem="AC stopped cooling",
        desired_outcome="it working this week",
    )
    decision = SalesPolicyEngine().decide(profile, analysis, business_facts_available=True)
    assert decision.move is SalesMove.NURTURE_WITHOUT_PRESSURE
    assert decision.target_stage is SalesStage.FOLLOW_UP


def test_need_to_think_clearer_next_step_is_still_answered() -> None:
    analysis = DeterministicSalesTurnAnalyzer().analyze(
        source_message_id="msg-think-3",
        customer_message="A clearer next step would help",
        profile_context={
            "sales_stage": "OBJECTION_HANDLING",
            "active_objection_type": "NEED_TO_THINK",
            "active_objection_status": "ACTIVE",
        },
        conversation_context={},
    )
    assert analysis.objections[0].status is ObjectionStatus.DIAGNOSED
    assert analysis.objections[0].cause == "unclear_next_step"
    profile = _profile(
        stage=SalesStage.OBJECTION_HANDLING,
        current_problem="AC stopped cooling",
        desired_outcome="it working this week",
    )
    decision = SalesPolicyEngine().decide(profile, analysis, business_facts_available=True)
    assert decision.move is SalesMove.ANSWER_OBJECTION


def test_request_business_fact_phrase_does_not_hand_the_customer_to_a_person() -> None:
    text = phrase_approved_move(SalesMove.REQUEST_BUSINESS_FACT, safe_fallback="A person will call you.")
    folded = text.casefold()
    assert "confirm one detail with the business" in folded
    assert "call" not in folded
    assert "team member" not in folded
