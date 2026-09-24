"""Operator-triggered internal tasks -- not part of the tenant-facing API.

Currently three endpoints behind the same secret: stalled-lead follow-up
(plus contextual sales follow-up after a pause), CRM/SMS outbox delivery,
and commercial expiry. See DEPLOY.md.
"""

import hmac
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from src.domain.models import utc_now
from src.persistence.commercial_expiry import CommercialExpirySweep
from src.persistence.crm_board_service import CrmBoardService, apply_board_command
from src.persistence.crm_webhook_service import CrmWebhookService
from src.persistence.follow_up_service import FollowUpSweepResult, PersistentFollowUpRunner
from src.persistence.sales_contextual_follow_up import (
    PersistentSalesContextualFollowUpRunner,
    SalesContextualFollowUpSweepResult,
)
from src.persistence.sms_service import SmsService

from ..dependencies import ApplicationContainer, build_outreach_service, get_container, get_email_outreach_service
from ..errors import RequestDataError, UnauthorizedError

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
    email = get_email_outreach_service(container).deliver_due()
    build_outreach_service(container).sync_sent()
    parts = (crm, sms, board, email)
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
    if body.action in ("discard", "pause_outreach", "takeover"):
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
    return {"command_id": body.command_id, "action": body.action, "changed": changed}
