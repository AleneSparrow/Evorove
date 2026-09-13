"""Evorove WhatsApp addresses. Tests never call Twilio or Meta."""

from src.persistence.whatsapp_mouth import twilio_whatsapp_address


def test_twilio_whatsapp_address_prefixes_e164() -> None:
    assert twilio_whatsapp_address("+15551234567") == "whatsapp:+15551234567"


def test_twilio_whatsapp_address_keeps_existing_prefix() -> None:
    assert twilio_whatsapp_address("whatsapp:+15551234567") == "whatsapp:+15551234567"


def test_strip_whatsapp_address() -> None:
    from src.persistence.whatsapp_mouth import strip_whatsapp_address

    assert strip_whatsapp_address("whatsapp:+15551234567") == "+15551234567"
    assert strip_whatsapp_address("+15551234567") == "+15551234567"
