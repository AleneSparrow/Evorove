"""Operator-triggered internal tasks -- not part of the tenant-facing API.

Follow-up sweep, CRM/SMS outbox, commercial expiry, CRM board commands,
and Found-card ingest from the CRM journal. Same secret. See DEPLOY.md.
"""

import hmac
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from src.domain.found_person import FoundPersonRejected, parse_crm_found_card
from src.domain.models import utc_now
from src.persistence.commercial_expiry import CommercialExpirySweep
from src.persistence.crm_board_service import CrmBoardService, apply_board_command
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
    build_email_inbox_service,
    build_outreach_service,
    get_container,
    get_email_outreach_service,
    get_sms_service,
    get_unit_of_work_factory,
    get_whatsapp_mouth,
)
from ..errors import ConflictError, PublicApiError, RequestDataError, ResourceNotFoundError, UnauthorizedError
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
    board = CrmBoardService(
        container.unit_of_work_factory,
        crm_base_url=container.settings.crm_base_url,
        secret=container.settings.internal_task_secret,
    ).deliver_due()
    build_email_inbox_service(container).poll_all()  # replies first, so answers go out in this sweep
    email = get_email_outreach_service(container).deliver_due()
    build_outreach_service(container).sync_sent()
    parts = (crm, sms, touches, board, email)
    return {key: sum(part[key] for part in parts) for key in ("attempted", "sent", "failed")}


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


class LeadCommandRequest(BaseModel):
    """What evorove-crm's cycle_command_delivery POSTs for an owner board command."""

    command_id: str = Field(min_length=1, max_length=255)
    action: Literal["discard", "correct_identity", "pause_outreach", "takeover", "cold_assigned"]
    person_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=320)
    name: str | None = Field(default=None, max_length=255)


@router.post(
    "/businesses/{business_id}/lead-commands",
    summary="Apply an owner command from the CRM board to cycle 2",
)
def apply_lead_command(
    business_id: str,
    body: LeadCommandRequest,
    container: Annotated[ApplicationContainer, Depends(get_container)],
    x_internal_task_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _require_task_secret(container, x_internal_task_secret)
    outreach = build_outreach_service(container)
    if body.action == "cold_assigned":
        if not body.person_id:
            raise RequestDataError("cold_assigned needs person_id")
        status = outreach.assign_cold(
            business_id,
            person_id=body.person_id,
            email=body.email,
            phone=body.phone,
            name=body.name,
            reason=str(body.payload.get("reason") or ""),
            reason_source=str(body.payload.get("reason_source") or ""),
            hypothesis_id=body.payload.get("hypothesis_id"),
        )
        return {"command_id": body.command_id, "action": body.action, "changed": 1, "status": status}
    stopped = 0
    if body.action in ("discard", "pause_outreach"):
        stopped = outreach.stop(business_id, email=body.email, phone=body.phone)
    try:
        changed = stopped + apply_board_command(
            container.unit_of_work_factory,
            business_id,
            action=body.action,
            phone=body.phone,
            email=body.email,
            corrected={key: body.payload.get(key) for key in ("name", "phone", "email") if body.payload.get(key)},
        )
    except ValueError as exc:
        raise RequestDataError(str(exc)) from exc
    if body.action == "takeover":
        if not changed:
            return {"status": "ignored", "reason": "sale_takeover_forbidden"}
        return {"status": "applied", "action": "takeover"}
    return {"command_id": body.command_id, "action": body.action, "changed": changed}
