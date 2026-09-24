"""Owner review of cycle-2 first emails (roadmap step 14).

The owner reads every drafted first message for a person from the CRM Cold
tab, may edit it, and approves or skips it. Approved messages leave from the
business's own mailbox and appear on the CRM card right away.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.domain.auth import StaffUser
from src.persistence.outreach_service import OutreachError, OutreachService

from ..dependencies import BusinessIdPath, get_outreach_service, require_own_business
from ..errors import RequestDataError

router = APIRouter(prefix="/api/v1/businesses/{business_id}/outreach", tags=["outreach"])


class ApproveRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1, max_length=10000)


@router.get("/prospects")
def list_prospects(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[OutreachService, Depends(get_outreach_service)],
    status: Literal["drafted", "approved", "sent", "skipped", "stopped"] | None = None,
) -> list[dict[str, Any]]:
    return service.list(business_id, status)


@router.post("/prospects/{person_id}/approve")
def approve_prospect(
    business_id: BusinessIdPath,
    person_id: str,
    body: ApproveRequest,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[OutreachService, Depends(get_outreach_service)],
) -> dict[str, Any]:
    try:
        return service.approve(business_id, person_id, approved_by=user.email, subject=body.subject, body=body.body)
    except OutreachError as exc:
        raise RequestDataError(str(exc)) from exc


@router.post("/prospects/{person_id}/skip")
def skip_prospect(
    business_id: BusinessIdPath,
    person_id: str,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[OutreachService, Depends(get_outreach_service)],
) -> dict[str, Any]:
    try:
        return service.skip(business_id, person_id)
    except OutreachError as exc:
        raise RequestDataError(str(exc)) from exc
