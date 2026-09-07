"""Synchronous live sales turn: analyze, decide one move, phrase, validate, persist."""

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping, Protocol
from uuid import uuid4

from src.ai.errors import AIInvalidOutputError, AIProviderError
from src.domain.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    MessageDirection,
    MessageRole,
)
from src.domain.events import EventType
from src.domain.models import DecisionType, ProcessCase, ProcessEvent
from src.domain.qualification import QualificationReasonCode, QualificationResult
from src.domain.sales import (
    CustomerSalesProfile,
    FollowUpReason,
    SalesMove,
    SalesMoveDecision,
    SalesObjectionRecord,
    SalesTurn,
    SalesTurnAnalysis,
)
from src.domain.states import ProcessState
from src.engine.decision_router import DecisionRequest
from src.engine.process_engine import ProcessEngine
from src.engine.sales_live_turn import (
    DeterministicSalesTurnAnalyzer,
    booking_available_for_live_turn,
    combined_business_facts,
    discovery_prompt,
    merge_profile_from_analysis,
    operationally_qualified_for_commitment,
    phrase_approved_move,
)
from src.engine.sales_objections import (
    answer_prompt,
    diagnose_prompt,
    mark_addressed,
    matching_knowledge,
)
from src.engine.sales_owner_facts import PENDING_KEY, owner_listed_facts, with_pending_business_fact_request
from src.engine.sales_policy import SalesPolicyEngine
from src.engine.sales_response_validator import (
    SalesPolicyValidator,
    SalesResponseCandidate,
    SalesResponseValidationContext,
)
from src.persistence.errors import StaleCaseError
from src.persistence.repositories import UnitOfWork

from .commercial_service import CommercialWorkflowService


class _SmsSender(Protocol):
    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None: ...


_OWNER_RESUME_MOVES = frozenset({
    SalesMove.PRESENT_RELEVANT_VALUE,
    SalesMove.ANSWER_OBJECTION,
    SalesMove.ASK_FOR_COMMITMENT,
    SalesMove.CHECK_OBJECTION_RESOLUTION,
})
_HUMAN_OWNED = frozenset({
    ConversationStatus.HUMAN_TAKEOVER_REQUESTED,
    ConversationStatus.HUMAN_TAKEOVER_ACTIVE,
})


class _SalesAnalyzer(Protocol):
    def analyze(
        self,
        *,
        source_message_id: str,
        customer_message: str,
        profile_context: Mapping[str, Any],
        conversation_context: Mapping[str, Any],
    ) -> SalesTurnAnalysis | Any: ...


class _SalesGenerator(Protocol):
    def generate(self, value: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class SalesLiveTurnResult:
    message_text: str
    reason: str
    process_state: ProcessState
    move: SalesMove
    requires_human: bool


class SalesLiveTurnService:
    """Drive one customer-facing sales turn inside the conversation transaction."""

    def __init__(
        self,
        *,
        analyzer: _SalesAnalyzer | None = None,
        response_generator: _SalesGenerator | None = None,
        commercial: CommercialWorkflowService | None = None,
        process_engine: ProcessEngine | None = None,
        policy: SalesPolicyEngine | None = None,
        validator: SalesPolicyValidator | None = None,
    ) -> None:
        self._analyzer = analyzer or DeterministicSalesTurnAnalyzer()
        self._generator = response_generator
        self._commercial = commercial or CommercialWorkflowService()
        self._process_engine = process_engine or ProcessEngine()
        self._policy = policy or SalesPolicyEngine()
        self._validator = validator or SalesPolicyValidator()
        self._fallback_analyzer = DeterministicSalesTurnAnalyzer()

    def run(
        self,
        uow: UnitOfWork,
        conversation: Conversation,
        case: ProcessCase,
        dna: Mapping[str, Any],
        qualification: QualificationResult,
        *,
        source_message_id: str,
        customer_text: str,
        prior_messages: tuple[ConversationMessage, ...],
        occurred_at: datetime,
    ) -> SalesLiveTurnResult:
        profile = uow.sales_profiles.get(
            conversation.business_id, case.case_id, for_update=True
        ) or CustomerSalesProfile(conversation.business_id, case.case_id)
        analysis = self._analyze(
            source_message_id=source_message_id,
            customer_text=customer_text,
            profile=profile,
            prior_messages=prior_messages,
        )
        merged = merge_profile_from_analysis(profile, analysis)
        knowledge = uow.sales_knowledge.list_approved(conversation.business_id)
        active_objection = analysis.objections[0] if analysis.objections else merged.active_objection
        objection_knowledge = matching_knowledge(knowledge, active_objection)
        booking_available = booking_available_for_live_turn(qualification, merged, analysis)
        facts = combined_business_facts(dna, qualification.service_id, merged)
        decision = self._policy.decide(
            merged,
            analysis,
            approved_knowledge_available=bool(objection_knowledge),
            business_facts_available=bool(facts),
            booking_available=booking_available,
            operational_intake_incomplete=not operationally_qualified_for_commitment(
                qualification
            ),
        )
        handoff_text = self._handoff_text(dna)
        if decision.move is SalesMove.HANDOFF_TO_HUMAN or decision.requires_human:
            self._transition_process(
                uow, case, ProcessState.NEEDS_HUMAN, occurred_at, decision.reason_code,
                requires_human=True,
            )
            persisted = replace(merged, stage=decision.target_stage, last_move=decision.move)
            self._persist_turn(
                uow, conversation, case, profile, persisted, analysis, decision,
                knowledge_ids=(), validation={"handoff": True}, occurred_at=occurred_at,
                source_message_id=source_message_id,
            )
            return SalesLiveTurnResult(
                handoff_text, decision.reason_code, case.current_state, decision.move, True,
            )

        if decision.move is SalesMove.OFFER_BOOKING_SLOTS:
            self._transition_process(
                uow, case, ProcessState.QUALIFIED, occurred_at, decision.reason_code,
            )
            commercial = self._commercial.initialize(
                uow, case, dna, conversation.metadata, occurred_at=occurred_at,
            )
            persisted = replace(merged, stage=decision.target_stage, last_move=decision.move)
            self._persist_turn(
                uow, conversation, case, profile, persisted, analysis, decision,
                knowledge_ids=tuple(card.knowledge_id for card in knowledge),
                validation={"commercial": commercial.reason}, occurred_at=occurred_at,
                source_message_id=source_message_id,
            )
            return SalesLiveTurnResult(
                commercial.message_text,
                commercial.reason,
                case.current_state,
                decision.move,
                commercial.requires_human,
            )

        callback_recorded = False
        if decision.move is SalesMove.SCHEDULE_CALLBACK:
            merged = self._execute_callback(
                uow, conversation, case, merged, analysis,
                occurred_at=occurred_at, source_message_id=source_message_id,
            )
            callback_recorded = True
            self._stamp_sales_follow_up_reason(
                uow, case, FollowUpReason.CALLBACK_REQUESTED, occurred_at,
            )
        elif decision.move is SalesMove.REQUEST_BUSINESS_FACT:
            merged = self._execute_business_fact_request(
                uow, conversation, case, merged, decision,
                occurred_at=occurred_at, source_message_id=source_message_id,
            )
        elif decision.move is SalesMove.NURTURE_WITHOUT_PRESSURE:
            self._stamp_sales_follow_up_reason(
                uow, case, FollowUpReason.OBJECTION_DEFERRED, occurred_at,
            )

        turn_knowledge = objection_knowledge if decision.knowledge_required else knowledge
        message_text, validation = self._phrase_and_validate(
            decision, analysis, turn_knowledge, customer_text, conversation, case,
            handoff_text, merged, qualification, dna,
            callback_recorded=callback_recorded,
        )
        if callback_recorded:
            validation = {**validation, "callback": True}
        persisted = replace(
            merged,
            stage=decision.target_stage,
            last_move=decision.move,
            active_objection=mark_addressed(merged.active_objection, decision.move),
        )
        self._persist_turn(
            uow, conversation, case, profile, persisted, analysis, decision,
            knowledge_ids=tuple(card.knowledge_id for card in turn_knowledge),
            business_fact_ids=tuple(fact_id for fact_id, _ in combined_business_facts(
                dna, qualification.service_id, persisted,
            )),
            validation=validation, occurred_at=occurred_at,
            source_message_id=source_message_id,
        )
        return SalesLiveTurnResult(
            message_text, decision.reason_code, case.current_state, decision.move, False,
        )

    def resume_after_owner_fact(
        self,
        uow: UnitOfWork,
        case: ProcessCase,
        dna: Mapping[str, Any],
        *,
        occurred_at: datetime,
        sms_service: _SmsSender | None = None,
    ) -> SalesLiveTurnResult | None:
        """Continue in the same channel after the owner supplies a missing fact.

        Does not wait for the next inbound customer message. Does not take
        over the conversation, change ProcessState, or invent a customer turn.
        """

        conversation = _active_conversation(uow, case.business_id, case.case_id)
        if conversation is None:
            return None
        profile = uow.sales_profiles.get(case.business_id, case.case_id, for_update=True)
        if profile is None:
            return None
        owner_facts = owner_listed_facts(profile)
        if not owner_facts:
            return None
        owner_fact_id, _owner_fact_text = owner_facts[-1]
        source_message_id = f"owner-fact-resume:{owner_fact_id}"
        existing = uow.events.list_for_case(case.business_id, case.case_id)
        already_recorded = any(
            event.event_type == EventType.BUSINESS_FACT_RESUMED
            and event.payload.get("source_message_id") == source_message_id
            for event in existing
        )
        if already_recorded:
            return None

        analysis = SalesTurnAnalysis(
            observed_stage=profile.stage,
            confidence=1.0,
            objections=(() if profile.active_objection is None else (profile.active_objection,)),
            commitment_level=profile.commitment_level,
            requested_callback_at=profile.preferred_contact_at,
            metadata={"owner_fact_resume": True, "business_fact_id": owner_fact_id},
        )
        knowledge = uow.sales_knowledge.list_approved(case.business_id)
        active_objection = analysis.objections[0] if analysis.objections else profile.active_objection
        objection_knowledge = matching_knowledge(knowledge, active_objection)
        qualification = _qualification_for_resume(case)
        decision = self._policy.decide(
            profile,
            analysis,
            approved_knowledge_available=bool(objection_knowledge),
            business_facts_available=bool(
                combined_business_facts(dna, qualification.service_id, profile)
            ),
            booking_available=False,
            operational_intake_incomplete=False,
        )
        if decision.move not in _OWNER_RESUME_MOVES or decision.requires_human:
            return None

        handoff_text = self._handoff_text(dna)
        turn_knowledge = objection_knowledge if decision.knowledge_required else knowledge
        message_text, validation = self._phrase_and_validate(
            decision, analysis, turn_knowledge, "", conversation, case,
            handoff_text, profile, qualification, dna,
        )
        persisted = replace(
            profile,
            stage=decision.target_stage,
            last_move=decision.move,
            active_objection=mark_addressed(profile.active_objection, decision.move),
        )
        self._persist_turn(
            uow, conversation, case, profile, persisted, analysis, decision,
            knowledge_ids=tuple(card.knowledge_id for card in turn_knowledge),
            business_fact_ids=tuple(
                fact_id for fact_id, _text in combined_business_facts(
                    dna, qualification.service_id, persisted,
                )
            ),
            validation=validation, occurred_at=occurred_at,
            source_message_id=source_message_id,
        )
        uow.events.add(
            case.business_id,
            case.case_id,
            ProcessEvent(
                EventType.BUSINESS_FACT_RESUMED,
                occurred_at=occurred_at,
                source="sales_live_turn",
                payload={
                    "reason": decision.reason_code,
                    "move": decision.move.value,
                    "source_message_id": source_message_id,
                    "conversation_id": conversation.conversation_id,
                    "business_fact_id": owner_fact_id,
                },
            ),
        )
        _deliver_resume(
            uow, conversation, case, message_text,
            source_message_id=source_message_id,
            occurred_at=occurred_at,
            sms_service=sms_service,
        )
        return SalesLiveTurnResult(
            message_text, decision.reason_code, case.current_state, decision.move, False,
        )

    def _analyze(
        self,
        *,
        source_message_id: str,
        customer_text: str,
        profile: CustomerSalesProfile,
        prior_messages: tuple[ConversationMessage, ...],
    ) -> SalesTurnAnalysis:
        context = {
            "sales_stage": profile.stage.value,
            "customer_goal": profile.customer_goal,
            "current_problem": profile.current_problem,
            "desired_outcome": profile.desired_outcome,
            "decision_criteria": list(profile.decision_criteria),
            "commitment_level": profile.commitment_level.value,
            "active_objection_type": (
                None if profile.active_objection is None
                else profile.active_objection.objection_type.value
            ),
            "active_objection_status": (
                None if profile.active_objection is None
                else profile.active_objection.status.value
            ),
            "active_objection_cause": (
                None if profile.active_objection is None
                else profile.active_objection.cause
            ),
        }
        conversation_context = {
            "recent_messages": [
                {"role": item.role.value, "text": item.text}
                for item in prior_messages
                if item.role in {MessageRole.CUSTOMER, MessageRole.ASSISTANT}
            ]
        }
        try:
            analyzed = self._analyzer.analyze(
                source_message_id=source_message_id,
                customer_message=customer_text,
                profile_context=context,
                conversation_context=conversation_context,
            )
        except (AIProviderError, AIInvalidOutputError):
            analyzed = self._fallback_analyzer.analyze(
                source_message_id=source_message_id,
                customer_message=customer_text,
                profile_context=context,
                conversation_context=conversation_context,
            )
        return analyzed.analysis if hasattr(analyzed, "analysis") else analyzed

    def _phrase_and_validate(
        self,
        decision: SalesMoveDecision,
        analysis: SalesTurnAnalysis,
        knowledge: tuple[Any, ...],
        customer_text: str,
        conversation: Conversation,
        case: ProcessCase,
        handoff_text: str,
        profile: CustomerSalesProfile,
        qualification: QualificationResult,
        dna: Mapping[str, Any],
        *,
        callback_recorded: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        evidence = tuple(item.evidence for item in analysis.signals) + tuple(
            item.evidence for item in analysis.objections
        )
        evidence_map = {f"evidence-{index}": item.excerpt for index, item in enumerate(evidence, start=1)}
        knowledge_map = {card.knowledge_id: card for card in knowledge}
        fallback = (
            handoff_text if decision.move is SalesMove.HANDOFF_TO_HUMAN
            else discovery_prompt(profile, qualification, dna)
            if decision.move is SalesMove.ASK_DISCOVERY_QUESTION
            else diagnose_prompt(profile.active_objection)
            if decision.move is SalesMove.DIAGNOSE_OBJECTION
            else answer_prompt(knowledge, phrase_approved_move(decision.move, safe_fallback=handoff_text))
            if decision.move is SalesMove.ANSWER_OBJECTION
            else phrase_approved_move(decision.move, safe_fallback=handoff_text)
        )
        candidate = SalesResponseCandidate(
            message_text=fallback,
            move=decision.move,
            knowledge_ids=(
                tuple(card.knowledge_id for card in knowledge)
                if decision.knowledge_required else ()
            ),
            used_safe_fallback=decision.move is SalesMove.HANDOFF_TO_HUMAN,
        )
        if self._generator is not None:
            try:
                from src.ai.sales_response_adapter import to_sales_response_candidate
                from src.ai.sales_response_generator import SalesResponseGenerationInput

                generated = self._generator.generate(SalesResponseGenerationInput(
                    approved_move=decision.move,
                    sales_stage=decision.target_stage,
                    channel=conversation.channel,
                    customer_tone="neutral",
                    knowledge_cards=[
                        {"knowledge_id": card.knowledge_id, "principle": card.principle}
                        for card in knowledge
                    ],
                    business_facts=[
                        {"business_fact_id": fact_id, "text": text}
                        for fact_id, text in combined_business_facts(
                            dna, qualification.service_id, profile
                        )
                    ],
                    customer_evidence=[
                        {"evidence_id": key, "text": value} for key, value in evidence_map.items()
                    ],
                    handoff_template=handoff_text,
                    safe_fallback_text=fallback,
                    conversation_context={"case_state": case.current_state.value},
                    customer_message=customer_text,
                ))
                candidate = to_sales_response_candidate(generated.output)
            except (AIProviderError, AIInvalidOutputError, AttributeError):
                candidate = SalesResponseCandidate(
                    message_text=fallback, move=decision.move, used_safe_fallback=True,
                )
        fact_map = dict(combined_business_facts(dna, qualification.service_id, profile))
        context = SalesResponseValidationContext(
            approved_move=decision.move,
            approved_knowledge=frozenset(knowledge_map),
            approved_business_facts=fact_map,
            customer_evidence=evidence_map,
            safe_fallback=fallback,
            knowledge_required=decision.knowledge_required,
            booking_available=False,
            callback_at=analysis.requested_callback_at or profile.preferred_contact_at,
            callback_recorded=callback_recorded,
            human_takeover_active=decision.requires_human,
        )
        result = self._validator.validate(candidate, context)
        return result.message_text, {
            "valid": result.valid,
            "violations": list(result.violations),
            "used_fallback": result.used_fallback,
        }

    def _persist_turn(
        self,
        uow: UnitOfWork,
        conversation: Conversation,
        case: ProcessCase,
        previous: CustomerSalesProfile,
        persisted: CustomerSalesProfile,
        analysis: SalesTurnAnalysis,
        decision: SalesMoveDecision,
        *,
        knowledge_ids: tuple[str, ...],
        validation: Mapping[str, Any],
        occurred_at: datetime,
        source_message_id: str,
        business_fact_ids: tuple[str, ...] = (),
    ) -> None:
        current = uow.sales_profiles.get(conversation.business_id, case.case_id, for_update=True)
        if current is None:
            uow.sales_profiles.add(persisted, now=occurred_at)
        else:
            uow.sales_profiles.save(
                replace(persisted, version=current.version), current.version, now=occurred_at,
            )
        known_sources = {
            item.objection.evidence.source_message_id
            for item in uow.sales_objections.list_for_case(conversation.business_id, case.case_id)
        }
        for objection in analysis.objections:
            source_id = objection.evidence.source_message_id
            if source_id in known_sources:
                continue
            uow.sales_objections.add(SalesObjectionRecord(
                str(uuid4()), conversation.business_id, case.case_id, objection,
                occurred_at, occurred_at,
            ))
            known_sources.add(source_id)
        playbook = uow.sales_playbooks.get_active(conversation.business_id)
        evidence = tuple(item.evidence for item in analysis.signals) + tuple(
            item.evidence for item in analysis.objections
        )
        uow.sales_turns.add(SalesTurn(
            turn_id=str(uuid4()),
            business_id=conversation.business_id,
            case_id=case.case_id,
            conversation_id=conversation.conversation_id,
            source_message_id=source_message_id,
            playbook_version=None if playbook is None else playbook.version,
            stage_before=previous.stage,
            stage_after=decision.target_stage,
            move=decision.move,
            reason_code=decision.reason_code,
            knowledge_ids=knowledge_ids,
            business_fact_ids=business_fact_ids,
            customer_evidence=evidence,
            analysis={
                "confidence": analysis.confidence,
                "recommended_moves": [item.value for item in analysis.recommended_moves],
            },
            validation=dict(validation),
            created_at=occurred_at,
        ))

    def _stamp_sales_follow_up_reason(
        self,
        uow: UnitOfWork,
        case: ProcessCase,
        reason: FollowUpReason,
        occurred_at: datetime,
    ) -> None:
        """Mark the case as owned by sales follow-up without touching ProcessState."""

        expected = case.version
        case.metadata["sales_follow_up_reason"] = reason.value
        case.updated_at = occurred_at
        uow.cases.save(case, expected)

    def _execute_business_fact_request(
        self,
        uow: UnitOfWork,
        conversation: Conversation,
        case: ProcessCase,
        profile: CustomerSalesProfile,
        decision: SalesMoveDecision,
        *,
        occurred_at: datetime,
        source_message_id: str,
    ) -> CustomerSalesProfile:
        """Ask the owner for a missing fact. The customer stays with the engine."""

        updated = with_pending_business_fact_request(
            profile, reason_code=decision.reason_code, requested_at=occurred_at,
        )
        existing = uow.events.list_for_case(conversation.business_id, case.case_id)
        already_recorded = any(
            event.event_type == EventType.BUSINESS_FACT_REQUESTED
            and event.payload.get("source_message_id") == source_message_id
            for event in existing
        )
        pending = updated.metadata.get(PENDING_KEY)
        needed_for = pending.get("needed_for") if isinstance(pending, Mapping) else None
        if not already_recorded:
            uow.events.add(
                conversation.business_id,
                case.case_id,
                ProcessEvent(
                    EventType.BUSINESS_FACT_REQUESTED,
                    occurred_at=occurred_at,
                    source="sales_live_turn",
                    payload={
                        "reason": decision.reason_code,
                        "needed_for": needed_for,
                        "source_message_id": source_message_id,
                        "conversation_id": conversation.conversation_id,
                    },
                ),
            )
        return updated

    def _execute_callback(
        self,
        uow: UnitOfWork,
        conversation: Conversation,
        case: ProcessCase,
        profile: CustomerSalesProfile,
        analysis: SalesTurnAnalysis,
        *,
        occurred_at: datetime,
        source_message_id: str,
    ) -> CustomerSalesProfile:
        """Record that the engine will continue in-channel. Not a staff call or CRM task."""

        window = next(
            (signal.value for signal in analysis.signals if signal.kind == "preferred_contact_time"),
            None,
        )
        metadata = dict(profile.metadata)
        metadata["callback_status"] = "requested"
        metadata["callback_source_message_id"] = source_message_id
        if window:
            metadata["preferred_contact_time"] = window
        existing = uow.events.list_for_case(conversation.business_id, case.case_id)
        already_recorded = any(
            event.event_type == EventType.CALLBACK_REQUESTED
            and event.payload.get("source_message_id") == source_message_id
            for event in existing
        )
        if not already_recorded:
            uow.events.add(
                conversation.business_id,
                case.case_id,
                ProcessEvent(
                    EventType.CALLBACK_REQUESTED,
                    occurred_at=occurred_at,
                    source="sales_live_turn",
                    payload={
                        "reason": "customer_requested_callback",
                        "requested_window": window,
                        "callback_at": (
                            None if analysis.requested_callback_at is None
                            else analysis.requested_callback_at.isoformat()
                        ),
                        "source_message_id": source_message_id,
                        "conversation_id": conversation.conversation_id,
                    },
                ),
            )
        return replace(
            profile,
            preferred_contact_at=analysis.requested_callback_at or profile.preferred_contact_at,
            metadata=metadata,
        )

    def _transition_process(
        self,
        uow: UnitOfWork,
        case: ProcessCase,
        target: ProcessState,
        occurred_at: datetime,
        reason: str,
        *,
        requires_human: bool = False,
    ) -> None:
        expected = case.version
        existing_event_count = len(case.event_history)
        decision_type = DecisionType.HUMAN if requires_human else DecisionType.RULE
        requested = ProcessState.QUALIFIED if requires_human else target
        event = ProcessEvent(
            EventType.TRIGGER_RECEIVED,
            occurred_at=occurred_at,
            source="sales_live_turn",
            payload={"reason": reason, "requested_target": requested.value},
        )
        self._process_engine.receive(case, event, DecisionRequest(decision_type, requested))
        uow.cases.save(case, expected)
        uow.events.add_many(
            case.business_id, case.case_id, case.event_history[existing_event_count:]
        )

    @staticmethod
    def _handoff_text(dna: Mapping[str, Any]) -> str:
        escalation = dna.get("human_escalation", {})
        message = escalation.get("customer_message") if isinstance(escalation, Mapping) else None
        if isinstance(message, str) and message.strip():
            return message.strip()
        return "A team member will follow up with you."


def _active_conversation(uow: UnitOfWork, business_id: str, case_id: str) -> Conversation | None:
    candidates = [
        conversation for conversation in uow.conversations.list_for_case(business_id, case_id)
        if conversation.status is ConversationStatus.AI_ACTIVE
        and conversation.status not in _HUMAN_OWNED
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.last_activity_at)


def _qualification_for_resume(case: ProcessCase) -> QualificationResult:
    service_id = case.lead.attributes.get("service_requested")
    if not isinstance(service_id, str) or not service_id.strip():
        service_id = None
    return QualificationResult(
        qualified=True,
        reasons=("Owner supplied a missing business fact",),
        reason_codes=(QualificationReasonCode.QUALIFIED,),
        missing_fields=(),
        unanswered_questions=(),
        confidence=1.0,
        recommended_next_state=ProcessState.QUALIFIED,
        requires_human=False,
        booking_allowed=False,
        service_id=service_id,
    )


def _deliver_resume(
    uow: UnitOfWork,
    conversation: Conversation,
    case: ProcessCase,
    message_text: str,
    *,
    source_message_id: str,
    occurred_at: datetime,
    sms_service: _SmsSender | None,
) -> bool:
    delivered = conversation.channel.casefold() != "sms"
    if conversation.channel.casefold() == "sms" and sms_service is not None:
        phone = case.lead.phone
        if phone and case.lead.sms_consent:
            delivered = sms_service.send_outbound(
                conversation.business_id, to_number=phone, body=message_text,
            ) is not None
        else:
            delivered = False
    fingerprint = hashlib.sha256(message_text.encode("utf-8")).hexdigest()
    sequence = uow.conversation_messages.next_sequence(
        conversation.business_id, conversation.conversation_id,
    )
    uow.conversation_messages.add(
        ConversationMessage(
            message_id=str(uuid4()),
            business_id=conversation.business_id,
            conversation_id=conversation.conversation_id,
            sequence_number=sequence,
            direction=MessageDirection.OUTBOUND,
            role=MessageRole.ASSISTANT,
            text=message_text,
            created_at=occurred_at,
            external_message_id=source_message_id,
            content_fingerprint=fingerprint,
            metadata={"owner_fact_resume": True, "delivered": delivered},
        )
    )
    try:
        expected = conversation.version
        conversation.touch(occurred_at)
        uow.conversations.save(conversation, expected)
    except StaleCaseError:
        return delivered
    return delivered
