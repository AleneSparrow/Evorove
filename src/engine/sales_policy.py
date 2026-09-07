"""Deterministic next-move policy for sales conversations."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from src.domain.sales import (
    CommitmentLevel,
    CustomerSalesProfile,
    ObjectionStatus,
    SalesMove,
    SalesMoveDecision,
    SalesStage,
    SalesTurnAnalysis,
)


class InvalidSalesStageTransition(ValueError):
    """Raised when conversational sales progress violates the closed policy."""


SALES_STAGE_TRANSITIONS: dict[SalesStage, frozenset[SalesStage]] = {
    SalesStage.GREETING: frozenset({SalesStage.DISCOVERY, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.DISCOVERY: frozenset({SalesStage.NEEDS_CONFIRMED, SalesStage.NURTURE, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.NEEDS_CONFIRMED: frozenset({SalesStage.PRESENTATION, SalesStage.DISCOVERY, SalesStage.FOLLOW_UP, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.PRESENTATION: frozenset({SalesStage.OBJECTION_HANDLING, SalesStage.COMMITMENT, SalesStage.NURTURE, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.OBJECTION_HANDLING: frozenset({SalesStage.PRESENTATION, SalesStage.COMMITMENT, SalesStage.BOOKING, SalesStage.NURTURE, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.COMMITMENT: frozenset({SalesStage.BOOKING, SalesStage.OBJECTION_HANDLING, SalesStage.NURTURE, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.BOOKING: frozenset({SalesStage.WON, SalesStage.OBJECTION_HANDLING, SalesStage.FOLLOW_UP, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.NURTURE: frozenset({SalesStage.FOLLOW_UP, SalesStage.DISCOVERY, SalesStage.PRESENTATION, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.FOLLOW_UP: frozenset({SalesStage.DISCOVERY, SalesStage.PRESENTATION, SalesStage.OBJECTION_HANDLING, SalesStage.COMMITMENT, SalesStage.BOOKING, SalesStage.HUMAN_REVIEW, SalesStage.LOST}),
    SalesStage.WON: frozenset(),
    SalesStage.LOST: frozenset({SalesStage.DISCOVERY}),
    SalesStage.HUMAN_REVIEW: frozenset(),
}


@dataclass(frozen=True, slots=True)
class SalesStageMachine:
    transitions: Mapping[SalesStage, frozenset[SalesStage]]

    def __init__(self, transitions: Mapping[SalesStage, frozenset[SalesStage]] | None = None) -> None:
        source = SALES_STAGE_TRANSITIONS if transitions is None else transitions
        if set(source) != set(SalesStage):
            raise ValueError("sales transitions must define every SalesStage exactly once")
        normalized: dict[SalesStage, frozenset[SalesStage]] = {}
        for stage, targets in source.items():
            if not isinstance(stage, SalesStage):
                raise TypeError("sales transition keys must be SalesStage values")
            frozen_targets = frozenset(targets)
            if any(not isinstance(target, SalesStage) for target in frozen_targets):
                raise TypeError("sales transition targets must be SalesStage values")
            if stage in frozen_targets:
                raise ValueError(f"sales self-transition is not allowed for {stage.value}")
            normalized[stage] = frozen_targets
        object.__setattr__(self, "transitions", MappingProxyType(normalized))

    def can_transition(self, current: SalesStage, target: SalesStage) -> bool:
        return target in self.transitions.get(current, frozenset()) and current is not target

    def validate(self, current: SalesStage, target: SalesStage) -> None:
        if not self.can_transition(current, target):
            raise InvalidSalesStageTransition(
                f"Cannot transition sales stage from {current.value} to {target.value}"
            )


class SalesPolicyEngine:
    """Select one governed move. AI recommendations never override precedence."""

    def decide(
        self,
        profile: CustomerSalesProfile,
        analysis: SalesTurnAnalysis,
        *,
        approved_knowledge_available: bool = False,
        business_facts_available: bool = False,
        booking_available: bool = False,
        operational_intake_incomplete: bool = False,
    ) -> SalesMoveDecision:
        if analysis.requires_human:
            return SalesMoveDecision(
                SalesMove.HANDOFF_TO_HUMAN,
                "analysis_requires_human",
                SalesStage.HUMAN_REVIEW,
                requires_human=True,
            )

        objection = profile.active_objection
        if analysis.objections:
            objection = analysis.objections[0]
        if objection is not None and objection.status not in {
            ObjectionStatus.RESOLVED,
            ObjectionStatus.DEFERRED,
        }:
            if objection.status is ObjectionStatus.HUMAN_REVIEW:
                return SalesMoveDecision(
                    SalesMove.HANDOFF_TO_HUMAN,
                    "objection_requires_human",
                    SalesStage.HUMAN_REVIEW,
                    requires_human=True,
                )
            if objection.cause is None:
                return SalesMoveDecision(
                    SalesMove.DIAGNOSE_OBJECTION,
                    "objection_cause_missing",
                    SalesStage.OBJECTION_HANDLING,
                )
            if objection.status in {ObjectionStatus.ACTIVE, ObjectionStatus.DIAGNOSED}:
                if not approved_knowledge_available and not business_facts_available:
                    return SalesMoveDecision(
                        SalesMove.REQUEST_BUSINESS_FACT,
                        "objection_answer_grounding_missing",
                        SalesStage.FOLLOW_UP,
                    )
                return SalesMoveDecision(
                    SalesMove.ANSWER_OBJECTION,
                    "diagnosed_objection_can_be_answered",
                    SalesStage.OBJECTION_HANDLING,
                    knowledge_required=approved_knowledge_available,
                )
            return SalesMoveDecision(
                SalesMove.CHECK_OBJECTION_RESOLUTION,
                "objection_answered_but_not_resolved",
                SalesStage.OBJECTION_HANDLING,
            )

        if _callback_requested(analysis):
            return SalesMoveDecision(
                SalesMove.SCHEDULE_CALLBACK,
                "customer_requested_callback",
                SalesStage.FOLLOW_UP,
            )

        if (
            objection is not None
            and objection.status is ObjectionStatus.DEFERRED
            and analysis.commitment_level is not CommitmentLevel.READY_FOR_NEXT_STEP
        ):
            return SalesMoveDecision(
                SalesMove.NURTURE_WITHOUT_PRESSURE,
                "objection_deferred_without_pressure",
                SalesStage.FOLLOW_UP,
            )

        if profile.stage is SalesStage.GREETING:
            return SalesMoveDecision(
                SalesMove.GREET_AND_SET_CONTEXT,
                "conversation_started",
                SalesStage.DISCOVERY,
            )

        if not profile.current_problem or not profile.desired_outcome:
            return SalesMoveDecision(
                SalesMove.ASK_DISCOVERY_QUESTION,
                "required_discovery_context_missing",
                SalesStage.DISCOVERY,
            )

        if operational_intake_incomplete:
            return SalesMoveDecision(
                SalesMove.ASK_DISCOVERY_QUESTION,
                "operational_intake_incomplete",
                profile.stage if profile.stage is not SalesStage.GREETING else SalesStage.DISCOVERY,
            )

        if profile.stage is SalesStage.DISCOVERY:
            return SalesMoveDecision(
                SalesMove.CONFIRM_CUSTOMER_NEED,
                "discovery_context_complete",
                SalesStage.NEEDS_CONFIRMED,
            )

        if profile.stage is SalesStage.NEEDS_CONFIRMED:
            if not approved_knowledge_available and not business_facts_available:
                return SalesMoveDecision(
                    SalesMove.REQUEST_BUSINESS_FACT,
                    "approved_presentation_knowledge_missing",
                    SalesStage.FOLLOW_UP,
                )
            return SalesMoveDecision(
                SalesMove.PRESENT_RELEVANT_VALUE,
                "confirmed_need_has_approved_value",
                SalesStage.PRESENTATION,
                knowledge_required=approved_knowledge_available,
            )

        if analysis.commitment_level is CommitmentLevel.READY_FOR_NEXT_STEP:
            if booking_available:
                return SalesMoveDecision(
                    SalesMove.OFFER_BOOKING_SLOTS,
                    "customer_ready_and_booking_available",
                    SalesStage.BOOKING,
                )
            return SalesMoveDecision(
                SalesMove.ASK_FOR_COMMITMENT,
                "customer_ready_without_booking_capability",
                SalesStage.COMMITMENT,
            )

        if profile.stage is SalesStage.PRESENTATION:
            return SalesMoveDecision(
                SalesMove.ASK_FOR_COMMITMENT,
                "need_presented_without_active_objection",
                SalesStage.COMMITMENT,
            )

        if profile.stage in {SalesStage.NURTURE, SalesStage.FOLLOW_UP}:
            return SalesMoveDecision(
                SalesMove.NURTURE_WITHOUT_PRESSURE,
                "customer_not_ready_for_next_step",
                SalesStage.NURTURE,
            )

        return SalesMoveDecision(
            SalesMove.ASK_FOR_COMMITMENT,
            "need_presented_without_active_objection",
            SalesStage.COMMITMENT,
        )


def _callback_requested(analysis: SalesTurnAnalysis) -> bool:
    """Evidence of a callback request authorizes the move; recommended_moves do not."""

    if analysis.requested_callback_at is not None:
        return True
    return any(signal.kind == "preferred_contact_time" for signal in analysis.signals)

