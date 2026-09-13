"""Operator-triggered internal tasks -- not part of the tenant-facing API.

Follow-up sweep, CRM/SMS outbox, commercial expiry, CRM board commands,
and Found-card ingest from the CRM journal. Same secret. See DEPLOY.md.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from src.domain.found_person import FoundPersonRejected, parse_crm_found_card
from src.domain.models import utc_now
from src.persistence.commercial_expiry import CommercialExpirySweep
from src.persistence.crm_touch_publisher import publisher_from_settings
from src.persistence.crm_webhook_service import CrmWebhookService
from src.persistence.errors import OutboundFirstTouchBlocked
from src.persistence.follow_up_service import FollowUpSweepResult, PersistentFollowUpRunner
from src.persistence.outbound_first_touch import OutboundFirstTouchService
from src.persistence.sales_contextual_follow_up import (
    PersistentSalesContextualFollowUpRunner,
    SalesContextualFollowUpSweepResult,
)
from src.persistence.sales_live_turn import SalesLiveTurnService
from src.persistence.sms_service import SmsService
from src.persistence.whatsapp_mouth import WhatsAppMouth

from ..dependencies import (
    ApplicationContainer,
    UnitOfWorkFactory,
    get_container,
    get_sms_service,
    get_whatsapp_mouth,
    get_unit_of_work_factory,
)
from ..errors import ConflictError, PublicApiError, ResourceNotFoundError, UnauthorizedError
from ..schemas import CrmFoundIngestRequest, OutboundFirstTouchResponse

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


def _require_task_secret(container: ApplicationContainer, provided: str | None) -> None:
    configured = container.settings.internal_task_secret
    if not configured:
        raise UnauthorizedError("Internal task endpoints are not enabled on this deployment")
    if not provided or not hmac.compare_digest(provided, configured):
        raise UnauthorizedError("Invalid or missing internal task secret")


@router.post(
    "/follow-up/run",
    summary="Run a proactive stalled-lead follow-up sweep across every business",
)
def run_follow_up_sweep(
    container: Annotated[ApplicationContainer, Depends(get_container)],
    x_internal_task_secret: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    _require_task_secret(container, x_internal_task_secret)
    now = utc_now()
    sms_service = SmsService(
        container.unit_of_work_factory,
        account_sid=container.settings.twilio_account_sid,
        auth_token=container.settings.twilio_auth_token,
        public_api_base_url=container.settings.public_api_base_url,
    )
    runner = PersistentFollowUpRunner(container.unit_of_work_factory, sms_service)
    result: FollowUpSweepResult = runner.run(now)
    sales_runner = PersistentSalesContextualFollowUpRunner(
        container.unit_of_work_factory,
        sms_service,
        response_generator=container.sales_response_generator,
    )
    sales: SalesContextualFollowUpSweepResult = sales_runner.run(now)
    return {
        "businesses_scanned": result.businesses_scanned,
        "cases_considered": result.cases_considered,
        "follow_ups_sent": result.follow_ups_sent,
        "follow_ups_skipped_stale": result.follow_ups_skipped_stale,
        "sales_cases_considered": sales.cases_considered,
        "sales_follow_ups_sent": sales.follow_ups_sent,
        "sales_follow_ups_skipped_no_channel": sales.follow_ups_skipped_no_channel,
        "sales_follow_ups_skipped_stale": sales.follow_ups_skipped_stale,
    }


@router.post(
    "/integrations/deliver",
    summary="Deliver due CRM and SMS-reply outbox rows",
)
def deliver_integration_outbox(
    container: Annotated[ApplicationContainer, Depends(get_container)],
    x_internal_task_secret: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    _require_task_secret(container, x_internal_task_secret)
    crm = CrmWebhookService(container.unit_of_work_factory).deliver_due()
    touches = publisher_from_settings(
        container.settings, container.unit_of_work_factory,
    ).deliver_due()
    sms_service = SmsService(
        container.unit_of_work_factory,
        account_sid=container.settings.twilio_account_sid,
        auth_token=container.settings.twilio_auth_token,
        public_api_base_url=container.settings.public_api_base_url,
    )
    sms = sms_service.deliver_due()
    return {
        "attempted": crm["attempted"] + sms["attempted"] + touches["attempted"],
        "sent": crm["sent"] + sms["sent"] + touches["sent"],
        "failed": crm["failed"] + sms["failed"] + touches["failed"],
    }


@router.post(
    "/commercial/expire",
    summary="Expire due quotes and payment requests across tenants",
)
def expire_due_commercial_items(
    container: Annotated[ApplicationContainer, Depends(get_container)],
    x_internal_task_secret: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    _require_task_secret(container, x_internal_task_secret)
    return CommercialExpirySweep(container.unit_of_work_factory).run(utc_now())


@router.post(
    "/businesses/{business_id}/found",
    response_model=OutboundFirstTouchResponse,
    summary="Ingest a CRM Found card and write the first outbound GREET",
)
def ingest_crm_found_card(
    business_id: str,
    body: CrmFoundIngestRequest,
    container: Annotated[ApplicationContainer, Depends(get_container)],
    unit_of_work_factory: Annotated[UnitOfWorkFactory, Depends(get_unit_of_work_factory)],
    sms_service: Annotated[SmsService, Depends(get_sms_service)],
    whatsapp_mouth: Annotated[WhatsAppMouth, Depends(get_whatsapp_mouth)],
    x_internal_task_secret: Annotated[str | None, Header()] = None,
) -> OutboundFirstTouchResponse:
    """Cycle 2 reads the journal card and writes. CRM does not send. No people search."""

    _require_task_secret(container, x_internal_task_secret)
    try:
        person = parse_crm_found_card(body.model_dump())
    except FoundPersonRejected as exc:
        raise PublicApiError(422, exc.code, str(exc)) from exc
    with container.unit_of_work_factory() as uow:
        if uow.businesses.get(business_id) is None:
            raise ResourceNotFoundError("business_not_found", "Business was not found")
    try:
        result = OutboundFirstTouchService(
            unit_of_work_factory,
            sms_service=sms_service,
            whatsapp_mouth=whatsapp_mouth,
            sales_live=SalesLiveTurnService(
                analyzer=container.sales_turn_analyzer,  # type: ignore[arg-type]
                response_generator=container.sales_response_generator,
                crm_touch_publisher=publisher_from_settings(
                    container.settings, container.unit_of_work_factory,
                ),
            ),
        ).start(
            business_id,
            idempotency_key=person.idempotency_key,
            reason=person.reason,
            source=person.source,
            channel=person.channel,
            consent_basis=person.consent_basis,
            name=person.name,
            phone=person.phone,
            email=person.email,
            person_id=person.person_id,
            preferred_channel=person.preferred_channel,
            messenger_id=person.messenger_id,
            gender=person.gender,
            region=person.region,
        )
    except FoundPersonRejected as exc:
        raise PublicApiError(422, exc.code, str(exc)) from exc
    except OutboundFirstTouchBlocked as exc:
        if exc.code in {"sms_suppressed", "conversation_already_active"}:
            raise ConflictError(exc.code, exc.public_message) from exc
        raise PublicApiError(422, exc.code, exc.public_message) from exc
    return OutboundFirstTouchResponse(
        case_id=result.case_id,
        conversation_id=result.conversation_id,
        lead_id=result.lead_id,
        move=result.move,
        message_text=result.message_text,
        delivered=result.delivered,
        process_state=result.process_state,
        duplicate=result.duplicate,
    )


@router.post(
    "/businesses/{business_id}/lead-commands",
    summary="Apply an owner board command from CRM",
)
def apply_lead_command(
    business_id: str,
    body: dict,
    container: Annotated[ApplicationContainer, Depends(get_container)],
    x_internal_task_secret: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    _require_task_secret(container, x_internal_task_secret)
    from src.domain.conversations import ConversationStatus
    from src.engine.lead_intake import LeadIntakeService

    action = str(body.get("action") or "")
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    phone = LeadIntakeService._normalize_phone(body.get("phone") or payload.get("phone"))
    email = LeadIntakeService._normalize_email(body.get("email") or payload.get("email"))
    with container.unit_of_work_factory() as uow:
        if uow.businesses.get(business_id) is None:
            from ..errors import ResourceNotFoundError

            raise ResourceNotFoundError("business_not_found", "Business was not found")
        lead = None
        if phone or email:
            lead = uow.leads.find_by_identity(business_id, phone, email)
        if lead is None:
            return {"status": "ignored", "reason": "person_not_in_sale"}
        case = uow.cases.find_active_for_lead(business_id, lead.lead_id)
        if action == "correct_identity":
            from dataclasses import replace

            uow.leads.save(
                business_id,
                replace(
                    lead,
                    name=str(payload.get("name") or lead.name or "") or lead.name,
                    phone=phone or lead.phone,
                    email=email or lead.email,
                ),
                utc_now(),
            )
        takeover_applied = False
        if case is not None:
            expected = case.version
            if action == "discard":
                case.metadata["board_discarded"] = True
            if action == "pause_outreach":
                case.metadata["board_pause_outreach"] = True
            case.updated_at = utc_now()
            uow.cases.save(case, expected)
            if action == "takeover":
                for conversation in uow.conversations.list_for_case(business_id, case.case_id):
                    if conversation.status is not ConversationStatus.HUMAN_TAKEOVER_REQUESTED:
                        continue
                    expected_conversation = conversation.version
                    conversation.set_status(ConversationStatus.HUMAN_TAKEOVER_ACTIVE, utc_now())
                    uow.conversations.save(conversation, expected_conversation)
                    takeover_applied = True
        uow.commit()
    if action == "takeover" and not takeover_applied:
        return {"status": "ignored", "reason": "sale_takeover_forbidden"}
    return {"status": "applied", "action": action}
