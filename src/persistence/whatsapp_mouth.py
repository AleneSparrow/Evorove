"""Evorove-owned WhatsApp send. Tenants never OAuth their Meta or IG accounts.

Uses Twilio on the Evorove account and `EVOROVE_WHATSAPP_FROM`. The customer
still sees Evorove for {business} in the GREET. STOP uses the same suppression
row as SMS for that E.164 number.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.persistence.sqlalchemy_models import SmsSuppressionRow
from src.persistence.twilio_client import TwilioAPIError, TwilioClient

if TYPE_CHECKING:
    from .repositories import UnitOfWorkFactory

LOGGER = logging.getLogger("uvicorn.error")
WHATSAPP_CHANNEL = "whatsapp"


def twilio_whatsapp_address(e164: str) -> str:
    raw = (e164 or "").strip()
    if raw.casefold().startswith("whatsapp:"):
        return raw
    return f"whatsapp:{raw}"


def strip_whatsapp_address(value: str) -> str:
    raw = (value or "").strip()
    if raw.casefold().startswith("whatsapp:"):
        return raw[9:].strip()
    return raw


class WhatsAppMouth:
    def __init__(
        self,
        unit_of_work_factory: "UnitOfWorkFactory | None" = None,
        *,
        from_number: str | None,
        account_sid: str | None,
        auth_token: str | None,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self._from_number = (from_number or "").strip() or None
        self._account_sid = account_sid
        self._auth_token = auth_token

    @property
    def configured(self) -> bool:
        return bool(self._from_number and self._account_sid and self._auth_token)

    def is_suppressed(self, business_id: str, phone_number: str) -> bool:
        if self.unit_of_work_factory is None:
            return False
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return False
            return session.get(SmsSuppressionRow, (business_id, phone_number)) is not None

    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None:
        if not self.configured:
            LOGGER.info("whatsapp_send_not_configured business_id=%s", business_id)
            return None
        if self.is_suppressed(business_id, to_number):
            LOGGER.info("whatsapp_send_suppressed business_id=%s", business_id)
            return None
        try:
            return TwilioClient(self._account_sid or "", self._auth_token or "").send_sms(
                from_number=twilio_whatsapp_address(self._from_number or ""),
                to_number=twilio_whatsapp_address(to_number),
                body=body,
            )
        except TwilioAPIError:
            LOGGER.exception("whatsapp_send_failed business_id=%s", business_id)
            return None
