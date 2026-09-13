"""SMS delivery: inbound Twilio webhook (public, signature-verified) and the
authenticated per-business status/retry endpoints.

The inbound webhook is deliberately NOT under `/api/v1/public/businesses/
{business_id}/...` like the web-chat conversation API -- Twilio doesn't know
a business_id, only the phone number a text arrived on, so the business is
resolved from that number via `SmsService.resolve_business_id_by_phone`.
Authenticity here rests entirely on the Twilio request signature (see
`twilio_client.validate_inbound_signature`), not on a hard-to-guess URL.

Reuses `PersistentLeadIntakeService` -- the same channel-agnostic engine
entry point `/api/v1/businesses/{business_id}/messages` uses -- rather than
the anonymous web-chat conversation flow, since a text message already
carries a stable identity (the sender's phone number) and has no browser
token to manage. Both channels are sales-led: completeness does not
qualify the case.
"""

from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response

from src.domain.auth import StaffUser
from src.domain.conversations import ConversationStatus
from src.domain.models import utc_now
from src.domain.qualification import IncomingMessage
from src.domain.sms_commands import classify_inbound_sms
from src.persistence.errors import WebhookSignatureError
from src.persistence.lead_intake import PersistentLeadIntakeService
from src.persistence.sms_service import (
    HELP_ACK,
    INBOUND_SMS_WEBHOOK_PATH,
    START_ACK,
    STOP_ACK,
    SmsProvisioningError,
    SmsService,
)
from src.persistence.sms_thread_service import SmsThreadService
from src.persistence.twilio_client import validate_inbound_signature
from src.persistence.whatsapp_mouth import WhatsAppMouth, strip_whatsapp_address

from ..dependencies import (
    ApplicationContainer,
    BusinessIdPath,
    get_container,
    get_intake_service,
    get_sms_service,
    get_sms_thread_service,
    get_whatsapp_mouth,
    require_own_business,
)
from ..errors import PublicApiError, RequestDataError, ResourceNotFoundError
from ..schemas import SmsStatusResponse

public_router = APIRouter(prefix="/api/v1/public/sms", tags=["sms"])
router = APIRouter(prefix="/api/v1/businesses/{business_id}/integrations", tags=["integrations"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
_WHATSAPP_PAUSED = frozenset({
    ConversationStatus.HUMAN_TAKEOVER_REQUESTED,
    ConversationStatus.HUMAN_TAKEOVER_ACTIVE,
})


def _receive_inbound_whatsapp(
    container: ApplicationContainer,
    sms_service: SmsService,
    intake_service: PersistentLeadIntakeService,
    whatsapp_mouth: WhatsAppMouth,
    *,
    from_number: str,
    body: str,
    message_sid: str,
) -> Response:
    """Continue an Evorove WhatsApp sale. Do not invent a new found person."""

    e164 = strip_whatsapp_address(from_number)
    with container.unit_of_work_factory() as uow:
        conversation = uow.conversations.find_open_by_channel_session(
            "whatsapp", f"wa:{e164}",
        )
        if conversation is None:
            return Response(content=_EMPTY_TWIML, media_type="application/xml")
        business_id = conversation.business_id
        paused = conversation.status in _WHATSAPP_PAUSED

    command = classify_inbound_sms(body)
    if command == "stop":
        sms_service.opt_out(business_id, e164, inbound_message_id=message_sid)
        return Response(content=_EMPTY_TWIML, media_type="application/xml")
    if command in {"start", "help"}:
        return Response(content=_EMPTY_TWIML, media_type="application/xml")
    if paused:
        return Response(content=_EMPTY_TWIML, media_type="application/xml")

    message = IncomingMessage(
        business_id=business_id,
        channel="whatsapp",
        external_message_id=message_sid,
        raw_text=body,
        timestamp=utc_now(),
        phone=e164,
    )
    result = intake_service.receive(message, sales_led_conversation=True)
    if result.response is not None and not result.duplicate:
        whatsapp_mouth.send_outbound(
            business_id, to_number=e164, body=result.response.message_text,
        )
    return Response(content=_EMPTY_TWIML, media_type="application/xml")


class SmsProvisioningFailedError(PublicApiError):
    """502 -- we reached out (to Twilio, or just checked our own config) and
    the attempt to buy a number failed. `public_message` is the specific
    reason from `SmsProvisioningError`, shown as-is in Settings so the
    owner sees *why* instead of the button silently doing nothing."""

    def __init__(self, public_message: str) -> None:
        super().__init__(502, "sms_provisioning_failed", public_message)


@public_router.post("/inbound", status_code=200)
async def receive_inbound_sms(
    request: Request,
    container: Annotated[ApplicationContainer, Depends(get_container)],
    sms_service: Annotated[SmsService, Depends(get_sms_service)],
    intake_service: Annotated[PersistentLeadIntakeService, Depends(get_intake_service)],
    sms_threads: Annotated[SmsThreadService, Depends(get_sms_thread_service)],
    whatsapp_mouth: Annotated[WhatsAppMouth, Depends(get_whatsapp_mouth)],
    x_twilio_signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> Response:
    if not x_twilio_signature or not container.settings.twilio_auth_token:
        raise WebhookSignatureError("Missing X-Twilio-Signature header, or SMS is not configured")

    # Twilio sends application/x-www-form-urlencoded, so stdlib parsing is
    # sufficient and avoids making inbound production delivery depend on the
    # optional python-multipart package used for browser file uploads.
    raw_body = await request.body()
    form_params = dict(parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True))
    validation_url = f"{container.settings.public_api_base_url}{INBOUND_SMS_WEBHOOK_PATH}"
    if not validate_inbound_signature(
        container.settings.twilio_auth_token,
        url=validation_url,
        form_params=form_params,
        signature=x_twilio_signature,
    ):
        raise WebhookSignatureError("Twilio request signature did not match")

    from_number = form_params.get("From")
    to_number = form_params.get("To")
    body = form_params.get("Body", "")
    message_sid = form_params.get("MessageSid")
    if not from_number or not to_number or not message_sid:
        raise RequestDataError("Missing From/To/MessageSid in Twilio webhook payload")

    if from_number.casefold().startswith("whatsapp:") or to_number.casefold().startswith("whatsapp:"):
        return _receive_inbound_whatsapp(
            container,
            sms_service,
            intake_service,
            whatsapp_mouth,
            from_number=from_number,
            body=body,
            message_sid=message_sid,
        )

    business_id = sms_service.resolve_business_id_by_phone(to_number)
    if business_id is None:
        # A number Twilio still has registered but we no longer recognize --
        # nothing to route to. Acknowledge with empty TwiML so Twilio doesn't
        # retry; there's no business-scoped error channel to report this to.
        return Response(content=_EMPTY_TWIML, media_type="application/xml")

    command = classify_inbound_sms(body)
    if command == "stop":
        sms_service.opt_out(business_id, from_number, inbound_message_id=message_sid)
        sms_threads.record_command(
            business_id,
            from_number,
            body=body,
            inbound_message_id=message_sid,
            outbound_text=STOP_ACK,
            pause=True,
        )
        return Response(content=_EMPTY_TWIML, media_type="application/xml")
    if command == "start":
        sms_service.opt_in(business_id, from_number, inbound_message_id=message_sid)
        sms_threads.record_command(
            business_id,
            from_number,
            body=body,
            inbound_message_id=message_sid,
            outbound_text=START_ACK,
        )
        return Response(content=_EMPTY_TWIML, media_type="application/xml")
    if command == "help":
        sms_service.send_help(business_id, from_number, inbound_message_id=message_sid)
        sms_threads.record_command(
            business_id,
            from_number,
            body=body,
            inbound_message_id=message_sid,
            outbound_text=HELP_ACK,
        )
        return Response(content=_EMPTY_TWIML, media_type="application/xml")

    if sms_threads.is_paused(business_id, from_number):
        sms_threads.append_customer_message(
            business_id,
            from_number,
            body=body,
            inbound_message_id=message_sid,
        )
        return Response(content=_EMPTY_TWIML, media_type="application/xml")

    message = IncomingMessage(
        business_id=business_id,
        channel="sms",
        external_message_id=message_sid,
        raw_text=body,
        timestamp=utc_now(),
        phone=from_number,
    )
    result = intake_service.receive(message, sales_led_conversation=True)
    sms_threads.sync_from_intake(
        business_id,
        from_number,
        body=body,
        inbound_message_id=message_sid,
        intake=result,
    )
    # Intake replays the stored logical result for a duplicate MessageSid.
    # That is correct for state/audit idempotency, but a customer-facing SMS
    # is an external side effect and must not be repeated on a Twilio retry.
    if result.response is not None and not result.duplicate:
        sms_service.enqueue_reply(
            business_id,
            to_number=from_number,
            body=result.response.message_text,
            inbound_message_id=message_sid,
        )
    return Response(content=_EMPTY_TWIML, media_type="application/xml")


@router.get("/sms", response_model=SmsStatusResponse)
def get_sms_status(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[SmsService, Depends(get_sms_service)],
) -> SmsStatusResponse:
    return SmsStatusResponse(configured=service.configured, phone_number=service.get_number(business_id))


@router.post("/sms/provision", response_model=SmsStatusResponse)
def provision_sms_number(
    business_id: BusinessIdPath,
    user: Annotated[StaffUser, Depends(require_own_business)],
    service: Annotated[SmsService, Depends(get_sms_service)],
) -> SmsStatusResponse:
    """Provisioning is manual, not automatic on signup (each number is a real
    recurring Twilio charge). This is the only place a number gets bought --
    called by the Settings 'Set up SMS' button, and idempotently retried by
    the same button (relabelled 'Retry') if an earlier attempt failed (e.g.
    a Twilio hiccup) or no number exists yet."""
    if not service.configured:
        raise ResourceNotFoundError("sms_not_configured", "SMS delivery is not configured on this deployment")
    try:
        phone_number = service.provision_number_if_needed(business_id)
    except SmsProvisioningError as exc:
        raise SmsProvisioningFailedError(str(exc)) from exc
    return SmsStatusResponse(configured=True, phone_number=phone_number)
