"""Cycle 1 → 2 input: a found person the sale may write to.

This is not people search. A contact dump without a grounded reason is rejected.
Outbound consent is stricter than the inbound widget: never inferred.

Send mouths: sms | email | whatsapp. WhatsApp is Evorove's provider number,
not the tenant's Instagram/WhatsApp OAuth. Email send is still a later slice.
Social Direct (IG and the like) is never a mouth.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

ALLOWED_OUTBOUND_CHANNELS = frozenset({"sms", "email", "whatsapp"})
DECLARED_PREFERRED_CHANNELS = frozenset({"sms", "email", "whatsapp"})
SOCIAL_DIRECT_CHANNELS = frozenset({
    "instagram", "ig", "ig_direct", "facebook", "fb", "messenger",
    "tiktok", "twitter", "x", "linkedin", "threads",
})
SMS_CONSENT_BASIS = "prior_express_written"
EMAIL_CONSENT_BASIS = "email_opt_in"
WHATSAPP_CONSENT_BASIS = "whatsapp_opt_in"
ALLOWED_CONSENT_BASES = frozenset({
    SMS_CONSENT_BASIS, EMAIL_CONSENT_BASIS, WHATSAPP_CONSENT_BASIS,
})
# Widget inbound, a public post, or "we found them" is not a send basis.
REJECTED_CONSENT_BASES = frozenset({
    "inferred",
    "inbound_widget",
    "public_post",
    "found_person",
    "existing_customer_guess",
})
_CHANNEL_ALIASES = {
    "sms": "sms",
    "text": "sms",
    "email": "email",
    "whatsapp": "whatsapp",
    "wa": "whatsapp",
}


class FoundPersonRejected(ValueError):
    """Raised when the 1→2 payload cannot start an outbound first touch."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class FoundPerson:
    name: str | None
    phone: str | None
    email: str | None
    reason: str
    source: str
    channel: str
    consent_basis: str
    idempotency_key: str
    person_id: str | None = None
    preferred_channel: str | None = None
    messenger_id: str | None = None
    gender: str | None = None
    region: str | None = None

    @property
    def address(self) -> str:
        if self.channel in {"sms", "whatsapp"}:
            assert self.phone is not None
            return self.phone
        assert self.email is not None
        return self.email


def parse_crm_found_card(payload: Mapping[str, object]) -> FoundPerson:
    """CRM journal Found → cycle 2. This is not people search."""

    identity = payload.get("identity")
    nested = identity if isinstance(identity, Mapping) else {}
    person_id = _optional_text(payload.get("person_id"))
    if not person_id:
        raise FoundPersonRejected(
            "found_person_id_required",
            "A CRM Found card requires person_id",
        )
    return parse_found_person(
        idempotency_key=_optional_text(payload.get("idempotency_key")) or f"found:{person_id}",
        reason=_optional_text(payload.get("reason")) or "",
        source=_optional_text(payload.get("source")) or _optional_text(payload.get("found_source")) or "",
        channel=_optional_text(payload.get("channel")),
        consent_basis=_optional_text(payload.get("consent_basis")),
        name=_optional_text(payload.get("name")) or _optional_text(nested.get("name")),
        phone=_optional_text(payload.get("phone")) or _optional_text(nested.get("phone")),
        email=_optional_text(payload.get("email")) or _optional_text(nested.get("email")),
        person_id=person_id,
        preferred_channel=_optional_text(payload.get("preferred_channel")),
        messenger_id=(
            _optional_text(payload.get("messenger_id"))
            or _optional_text(nested.get("messenger_id"))
        ),
        gender=_stated_label(payload.get("gender")) or _stated_label(nested.get("gender")),
        region=(
            _stated_label(payload.get("region"))
            or _stated_label(nested.get("region"))
            or _stated_label(nested.get("state"))
        ),
    )


def parse_found_person(
    *,
    idempotency_key: str,
    reason: str,
    source: str,
    channel: str | None,
    consent_basis: str | None,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    person_id: str | None = None,
    preferred_channel: str | None = None,
    messenger_id: str | None = None,
    gender: str | None = None,
    region: str | None = None,
) -> FoundPerson:
    key = (idempotency_key or "").strip()
    if not key:
        raise FoundPersonRejected("idempotency_key_required", "An idempotency key is required")
    grounded = (reason or "").strip()
    if not _has_grounded_reason(grounded):
        raise FoundPersonRejected(
            "found_person_reason_required",
            "A grounded reason is required; a contact dump is not a found person",
        )
    origin = (source or "").strip()
    if not origin:
        raise FoundPersonRejected("found_person_source_required", "A source is required")
    send, preferred = _resolve_channels(channel, preferred_channel)
    basis = (consent_basis or "").strip().casefold()
    if not basis or basis in REJECTED_CONSENT_BASES:
        raise FoundPersonRejected(
            "outbound_consent_required",
            "Outbound first touch needs an explicit allowed consent basis; consent is never inferred",
        )
    if basis not in ALLOWED_CONSENT_BASES:
        raise FoundPersonRejected(
            "outbound_consent_required",
            "Outbound first touch needs an explicit allowed consent basis; consent is never inferred",
        )
    if send == "sms" and basis != SMS_CONSENT_BASIS:
        raise FoundPersonRejected(
            "outbound_consent_required",
            "SMS first touch requires prior express written consent",
        )
    if send == "email" and basis != EMAIL_CONSENT_BASIS:
        raise FoundPersonRejected(
            "outbound_consent_required",
            "Email first touch requires an explicit email opt-in",
        )
    if send == "whatsapp" and basis != WHATSAPP_CONSENT_BASIS:
        raise FoundPersonRejected(
            "outbound_consent_required",
            "WhatsApp first touch requires an explicit WhatsApp opt-in",
        )
    try:
        normalized_phone = _normalize_phone(phone)
        normalized_email = _normalize_email(email)
        cleaned_messenger = _normalize_messenger_id(messenger_id)
    except ValueError as exc:
        raise FoundPersonRejected("found_person_identity_invalid", str(exc)) from exc
    if send == "whatsapp":
        destination = whatsapp_destination(normalized_phone, cleaned_messenger)
        if not destination:
            raise FoundPersonRejected(
                "found_person_not_addressable",
                "WhatsApp first touch requires a phone number or WhatsApp messenger id",
            )
        normalized_phone = destination
    if send == "sms" and not normalized_phone:
        raise FoundPersonRejected(
            "found_person_not_addressable",
            "SMS first touch requires a phone number",
        )
    if send == "email" and not normalized_email:
        raise FoundPersonRejected(
            "found_person_not_addressable",
            "Email first touch requires an email address",
        )
    if not normalized_phone and not normalized_email:
        raise FoundPersonRejected(
            "found_person_not_addressable",
            "A found person must already be addressable by phone or email",
        )
    cleaned_name = name.strip() if isinstance(name, str) and name.strip() else None
    return FoundPerson(
        name=cleaned_name,
        phone=normalized_phone,
        email=normalized_email,
        reason=grounded,
        source=origin,
        channel=send,
        consent_basis=basis,
        idempotency_key=key,
        person_id=person_id.strip() if isinstance(person_id, str) and person_id.strip() else None,
        preferred_channel=preferred,
        messenger_id=cleaned_messenger,
        gender=_stated_label(gender),
        region=_stated_label(region),
    )


def _resolve_channels(
    channel: str | None, preferred_channel: str | None,
) -> tuple[str, str]:
    send = _normalize_channel_token(channel)
    preferred = _normalize_channel_token(preferred_channel)
    if not preferred:
        preferred = send
    if not send:
        send = preferred
    if send in SOCIAL_DIRECT_CHANNELS:
        raise FoundPersonRejected(
            "outbound_channel_invalid",
            "Social Direct is not an Evorove mouth; write from Evorove SMS, email, or WhatsApp",
        )
    if preferred and preferred in SOCIAL_DIRECT_CHANNELS:
        raise FoundPersonRejected(
            "preferred_channel_invalid",
            "preferred_channel must be sms, email, or whatsapp",
        )
    if not send:
        raise FoundPersonRejected(
            "outbound_channel_invalid",
            "Channel must be sms, email, or whatsapp",
        )
    if preferred and preferred not in DECLARED_PREFERRED_CHANNELS:
        raise FoundPersonRejected(
            "preferred_channel_invalid",
            "preferred_channel must be sms, email, or whatsapp",
        )
    if send not in ALLOWED_OUTBOUND_CHANNELS:
        raise FoundPersonRejected(
            "outbound_channel_invalid",
            "Channel must be sms, email, or whatsapp",
        )
    if not preferred:
        preferred = send
    return send, preferred


def whatsapp_destination(phone: str | None, messenger_id: str | None) -> str | None:
    """E.164 destination on Evorove's WhatsApp sender. Not an IG Direct thread."""

    if phone:
        return phone
    if not messenger_id:
        return None
    raw = messenger_id.strip()
    lower = raw.casefold()
    if lower.startswith("whatsapp:"):
        raw = raw[9:]
    elif lower.startswith("wa:"):
        raw = raw[3:]
    try:
        return _normalize_phone(raw)
    except ValueError:
        return None


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _stated_label(value: object) -> str | None:
    """Keep a cycle-1 / owner label. Never invent gender or region from a name."""
    cleaned = _optional_text(value)
    if cleaned is None or len(cleaned) > 80:
        return None
    return cleaned


def _normalize_channel_token(value: str | None) -> str:
    raw = (value or "").strip().casefold().replace("-", "_")
    if not raw:
        return ""
    return _CHANNEL_ALIASES.get(raw, raw)


def _has_grounded_reason(reason: str) -> bool:
    if len(reason) < 16:
        return False
    tokens = [token for token in reason.split() if token]
    if len(tokens) < 3:
        return False
    letters = sum(1 for character in reason if character.isalpha())
    return letters >= 10


def _normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise ValueError("email is not valid")
    return normalized


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    prefix = "+" if value.strip().startswith("+") else ""
    digits = "".join(character for character in value if character.isdigit())
    if not 7 <= len(digits) <= 15:
        raise ValueError("phone must contain between 7 and 15 digits")
    return f"{prefix}{digits}"


def _normalize_messenger_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 128:
        raise ValueError("messenger id is too long")
    return cleaned
