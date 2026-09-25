"""Cycle 2 → 3 handoff payload. CRM is the receiver; this repo shapes and POSTs it.

Do not include a calendar slot. The hour is booked in CRM.
"""

from typing import Any, Mapping

HOT_LEAD_HANDOFF_SCHEMA_VERSION = "1"
HOT_LEAD_SOURCE = "evorove"
ALLOWED_WAITING_CHANNELS = frozenset({"sms", "web_chat", "email"})
_CALENDAR_KEYS = frozenset({"slot_start_at", "start_at", "booking_id", "end_at"})
_CHANNEL_ALIASES = {
    "sms": "sms",
    "email": "email",
    "web_chat": "web_chat",
    "webchat": "web_chat",
    "widget": "web_chat",
    "chat": "web_chat",
    "web": "web_chat",
    "whatsapp": "sms",
    "wa": "sms",
}


def waiting_channel(channel: str) -> str:
    """Map a conversation channel onto the cycle-3 waiting-channel enum."""

    mapped = _CHANNEL_ALIASES.get((channel or "").strip().casefold().replace("-", "_"))
    if mapped is None:
        raise ValueError("waiting channel must be sms, web_chat, or email")
    return mapped


def build_hot_lead_handoff_payload(
    *,
    handoff_id: str,
    channel: str,
    service_id: str,
    evidence_excerpt: str,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    sales_profile_snapshot: Mapping[str, Any] | None = None,
    customer_location: str | None = None,
) -> dict[str, Any]:
    """Explicit receive contract for `/hot-leads` in evorove-crm."""

    if not handoff_id.strip():
        raise ValueError("handoff_id must not be empty")
    if channel not in ALLOWED_WAITING_CHANNELS:
        raise ValueError("waiting channel must be sms, web_chat, or email")
    if not service_id.strip():
        raise ValueError("agreed service_id is required")
    if not evidence_excerpt.strip():
        raise ValueError("readiness evidence is required")
    if not phone and not email:
        raise ValueError("a hot lead must already be addressable by phone or email")
    snapshot = dict(sales_profile_snapshot or {})
    if _CALENDAR_KEYS.intersection(snapshot):
        raise ValueError("sales profile snapshot must not include a calendar slot")
    payload = {
        "schema_version": HOT_LEAD_HANDOFF_SCHEMA_VERSION,
        "source": HOT_LEAD_SOURCE,
        "handoff_id": handoff_id,
        "channel": channel,
        "identity": {
            "name": name,
            "phone": phone,
            "email": email,
        },
        "service_id": service_id,
        "readiness": {
            "evidence_excerpt": evidence_excerpt,
            "signal": "ready_to_book",
        },
        "sales_profile_snapshot": snapshot,
        "customer_location": customer_location,
    }
    if _CALENDAR_KEYS.intersection(payload):
        raise ValueError("hot-lead handoff must not include a calendar slot")
    return payload


def try_build_hot_lead_handoff_payload(
    *,
    handoff_id: str,
    channel: str,
    service_id: str | None,
    evidence_excerpt: str,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    sales_profile_snapshot: Mapping[str, Any] | None = None,
    customer_location: str | None = None,
) -> dict[str, Any] | None:
    """Shape the 2→3 payload when the sale is ready. None if incomplete."""

    try:
        return build_hot_lead_handoff_payload(
            handoff_id=handoff_id,
            channel=waiting_channel(channel),
            service_id=service_id or "",
            evidence_excerpt=evidence_excerpt,
            name=name,
            phone=phone,
            email=email,
            sales_profile_snapshot=sales_profile_snapshot,
            customer_location=customer_location,
        )
    except ValueError:
        return None
