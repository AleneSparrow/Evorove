"""People tab of evorove.com: the four-tab board, served from the CRM service.

Same paths and shapes as the CRM's own owner routes, so the page code is the
same; the login, the business and the subscription check are evorove.com's.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.domain.auth import StaffUser
from src.domain.tenancy import Business
from src.persistence.crm_board_proxy import CrmBoardError, CrmBoardProxy

from ..dependencies import (
    ApplicationContainer,
    BusinessIdPath,
    get_container,
    require_active_subscription,
    resolve_business,
)
from ..errors import PublicApiError

router = APIRouter(prefix="/api/v1/businesses/{business_id}/board", tags=["board"])


class CommandRequest(BaseModel):
    action: Literal["discard", "correct_identity", "pause_outreach", "takeover"]
    name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=320)


class SearchRequest(BaseModel):
    site_url: str = Field(min_length=4, max_length=2048)


def get_board_proxy(container: Annotated[ApplicationContainer, Depends(get_container)]) -> CrmBoardProxy:
    return CrmBoardProxy(container.settings.crm_base_url, container.settings.internal_task_secret)


def _raise(exc: CrmBoardError) -> None:
    raise PublicApiError(exc.status, "board_unavailable" if exc.status >= 500 else "board_request_rejected", exc.message) from exc


@router.get("")
def list_board(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_active_subscription)],
    business: Annotated[Business, Depends(resolve_business)],
    proxy: Annotated[CrmBoardProxy, Depends(get_board_proxy)],
    tab: Literal["cold", "in_work", "offer_sent", "done"] = "cold",
) -> dict[str, Any]:
    try:
        proxy.ensure_business(business_id, business.name)
        return proxy.list_tab(business_id, tab)
    except CrmBoardError as exc:
        _raise(exc)


@router.get("/people/{person_id}")
def get_person(
    business_id: BusinessIdPath,
    person_id: str,
    user: Annotated[StaffUser, Depends(require_active_subscription)],
    proxy: Annotated[CrmBoardProxy, Depends(get_board_proxy)],
) -> dict[str, Any]:
    try:
        return proxy.person(business_id, person_id)
    except CrmBoardError as exc:
        _raise(exc)


@router.post("/people/{person_id}/commands")
def issue_command(
    business_id: BusinessIdPath,
    person_id: str,
    body: CommandRequest,
    user: Annotated[StaffUser, Depends(require_active_subscription)],
    proxy: Annotated[CrmBoardProxy, Depends(get_board_proxy)],
) -> dict[str, Any]:
    payload = {**body.model_dump(exclude_none=True), "approved_by": user.email}
    try:
        return proxy.command(business_id, person_id, payload)
    except CrmBoardError as exc:
        _raise(exc)


@router.post("/search")
def start_search(
    business_id: BusinessIdPath,
    body: SearchRequest,
    user: Annotated[StaffUser, Depends(require_active_subscription)],
    business: Annotated[Business, Depends(resolve_business)],
    proxy: Annotated[CrmBoardProxy, Depends(get_board_proxy)],
) -> dict[str, Any]:
    try:
        proxy.ensure_business(business_id, business.name)
        return proxy.start_search(business_id, body.site_url.strip())
    except CrmBoardError as exc:
        _raise(exc)


@router.get("/search")
def search_status(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_active_subscription)],
    proxy: Annotated[CrmBoardProxy, Depends(get_board_proxy)],
) -> dict[str, Any]:
    if not proxy.configured:
        return {"business_id": business_id, "status": "not_set_up", "site_url": None, "cold": 0, "last_run_at": None}
    try:
        return proxy.search_status(business_id)
    except CrmBoardError as exc:
        _raise(exc)
