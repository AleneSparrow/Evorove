"""Optional per-business CRM webhook (e.g. Clio) -- see CrmWebhookService.

Deliberately a dedicated resource, not folded into `/dna`: the webhook URL
is effectively a bearer secret and must never round-trip through the
Business-DNA read/write path (which flows into AI prompt context). The GET
here reports only whether one is configured -- never the URL itself.
"""

from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.domain.auth import StaffUser
from src.persistence.crm_webhook_service import CrmWebhookService
from src.persistence.email_outreach_service import (
    EmailOutreachError,
    EmailOutreachService,
    MailboxSettings,
    MailboxStatus,
)

from ..dependencies import (
    BusinessIdPath,
    get_crm_webhook_service,
    get_email_outreach_service,
    require_own_business,
)
from ..errors import RequestDataError
from ..schemas import CrmWebhookConfigureRequest, CrmWebhookStatusResponse

router = APIRouter(prefix="/api/v1/businesses/{business_id}/integrations", tags=["integrations"])


@router.get("/crm-webhook", response_model=CrmWebhookStatusResponse)
def get_crm_webhook_status(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[CrmWebhookService, Depends(get_crm_webhook_service)],
) -> CrmWebhookStatusResponse:
    return CrmWebhookStatusResponse(configured=service.is_configured(business_id))


@router.put("/crm-webhook", response_model=CrmWebhookStatusResponse)
def configure_crm_webhook(
    business_id: BusinessIdPath,
    body: CrmWebhookConfigureRequest,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[CrmWebhookService, Depends(get_crm_webhook_service)],
) -> CrmWebhookStatusResponse:
    try:
        service.configure(business_id, body.webhook_url)
    except ValueError as exc:
        raise RequestDataError(str(exc)) from exc
    return CrmWebhookStatusResponse(configured=True)


@router.delete("/crm-webhook", response_model=CrmWebhookStatusResponse)
def remove_crm_webhook(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[CrmWebhookService, Depends(get_crm_webhook_service)],
) -> CrmWebhookStatusResponse:
    service.remove(business_id)
    return CrmWebhookStatusResponse(configured=False)


class EmailConnectionRequest(BaseModel):
    """The business's own work mailbox for cycle-2 cold email. The password is
    write-only: it is encrypted at rest and never returned."""

    from_address: str = Field(min_length=3, max_length=320)
    from_name: str = Field(min_length=1, max_length=255)
    postal_address: str = Field(min_length=10, max_length=500)
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(ge=1, le=65535)
    smtp_security: Literal["ssl", "starttls"]
    smtp_username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    imap_host: str | None = Field(default=None, max_length=255)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    daily_limit: int = Field(default=30, ge=1, le=500)


class EmailConnectionStatusResponse(BaseModel):
    connected: bool
    from_address: str | None = None
    from_name: str | None = None
    smtp_host: str | None = None
    imap_host: str | None = None
    daily_limit: int | None = None
    todays_cap: int | None = None
    sent_today: int = 0


def _email_status(status: MailboxStatus) -> EmailConnectionStatusResponse:
    return EmailConnectionStatusResponse(**asdict(status))


@router.get("/email", response_model=EmailConnectionStatusResponse)
def get_email_connection(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[EmailOutreachService, Depends(get_email_outreach_service)],
) -> EmailConnectionStatusResponse:
    return _email_status(service.status(business_id))


@router.put("/email", response_model=EmailConnectionStatusResponse)
def connect_email(
    business_id: BusinessIdPath,
    body: EmailConnectionRequest,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[EmailOutreachService, Depends(get_email_outreach_service)],
) -> EmailConnectionStatusResponse:
    try:
        status = service.connect(business_id, MailboxSettings(**body.model_dump()))
    except EmailOutreachError as exc:
        raise RequestDataError(str(exc)) from exc
    return _email_status(status)


@router.delete("/email", response_model=EmailConnectionStatusResponse)
def disconnect_email(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[EmailOutreachService, Depends(get_email_outreach_service)],
) -> EmailConnectionStatusResponse:
    service.disconnect(business_id)
    return EmailConnectionStatusResponse(connected=False)
