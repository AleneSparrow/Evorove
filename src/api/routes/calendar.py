"""Owner-facing Google Calendar connection for the Settings page.

The owner connects her own Google account; BOOKED turns then write the real
hour into her calendar through the durable outbox (src/persistence/calendar_service.py).
The OAuth app is registered by the operator herself — see DEPLOY.md.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from src.domain.auth import StaffUser
from src.persistence.calendar_service import CalendarService

from ..dependencies import (
    BusinessIdPath,
    get_calendar_service,
    require_own_business,
)
from ..errors import PublicApiError, RequestDataError
from ..schemas import (
    CalendarCallbackRequest,
    CalendarConnectRequest,
    CalendarConnectResponse,
    CalendarStatusResponse,
)

router = APIRouter(prefix="/api/v1/businesses/{business_id}/calendar", tags=["calendar"])

_STATE_MESSAGES = {
    "calendar_not_enabled": "Calendar integration is not enabled on this deployment",
    "calendar_state_invalid": "The connect link is invalid; start over from Settings",
    "calendar_state_expired": "The connect link expired; start over from Settings",
    "calendar_state_mismatch": "The connect link belongs to a different business",
    "calendar_token_exchange_failed": "Google rejected the connect request; try again",
    "calendar_no_refresh_token": "Google did not issue a lasting grant; reconnect and allow access",
    "calendar_redirect_not_https": "The redirect address must be https",
}


def _map_connect_error(exc: ValueError) -> PublicApiError:
    code = str(exc)
    message = _STATE_MESSAGES.get(code, "Calendar connection failed")
    if code == "calendar_not_enabled":
        return PublicApiError(503, code, message)
    if code == "calendar_token_exchange_failed":
        return PublicApiError(502, code, message)
    if code == "calendar_state_mismatch":
        return PublicApiError(403, code, message)
    return RequestDataError(message)


@router.get("", response_model=CalendarStatusResponse)
def get_connection(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> CalendarStatusResponse:
    connection = service.get_connection(business_id)
    if connection is None:
        return CalendarStatusResponse(enabled=service.enabled, connected=False)
    return CalendarStatusResponse(
        enabled=service.enabled,
        connected=True,
        provider=connection["provider"],
        calendar_id=connection["calendar_id"],
        connected_at=connection["connected_at"],
    )


@router.post("/connect", response_model=CalendarConnectResponse)
def begin_connect(
    business_id: BusinessIdPath,
    body: CalendarConnectRequest,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> CalendarConnectResponse:
    try:
        auth_url = service.begin_connect(business_id, user.user_id, body.redirect_uri)
    except ValueError as exc:
        raise _map_connect_error(exc) from exc
    return CalendarConnectResponse(auth_url=auth_url)


@router.post("/callback", response_model=CalendarStatusResponse)
def complete_connect(
    business_id: BusinessIdPath,
    body: CalendarCallbackRequest,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> CalendarStatusResponse:
    try:
        service.complete_connect(business_id, body.state, body.code)
    except ValueError as exc:
        raise _map_connect_error(exc) from exc
    connection = service.get_connection(business_id)
    return CalendarStatusResponse(
        enabled=service.enabled,
        connected=True,
        provider=(connection or {}).get("provider", "google"),
        calendar_id=(connection or {}).get("calendar_id", "primary"),
        connected_at=(connection or {}).get("connected_at"),
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> Response:
    service.disconnect(business_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
