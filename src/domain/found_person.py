"""Cycle 1 → 2 input: a found person the sale may write to.

This is not people search. A contact dump without a grounded reason is rejected.
Outbound consent is stricter than the inbound widget: never inferred.
"""

import re
from dataclasses import dataclass

ALLOWED_OUTBOUND_CHANNELS = frozenset({"sms", "email"})
SMS_CONSENT_BASIS = "prior_express_written"
EMAIL_CONSENT_BASIS = "email_opt_in"
ALLOWED_CONSENT_BASES = frozenset({SMS_CONSENT_BASIS, EMAIL_CONSENT_BASIS})
# Widget inbound, a public post, or "we found them" is not a send basis.
REJECTED_CONSENT_BASES = frozenset({
    "inferred",
    "inbound_widget",
    "public_post",
    "found_person",
    "existing_customer_guess",
})


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

    @property
    def address(self) -> str:
        if self.channel == "sms":
            assert self.phone is not None
            return self.phone
        assert self.email is not None
        return self.email


def parse_found_person(
    *,
    idempotency_key: str,
    reason: str,
    source: str,
    channel: str,
    consent_basis: str | None,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
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
    route = (channel or "").strip().casefold()
    if route not in ALLOWED_OUTBOUND_CHANNELS:
        raise FoundPersonRejected("outbound_channel_invalid", "Channel must be sms or email")
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
    if route == "sms" and basis != SMS_CONSENT_BASIS:
        raise FoundPersonRejected(
            "outbound_consent_required",
            "SMS first touch requires prior express written consent",
        )
    if route == "email" and basis != EMAIL_CONSENT_BASIS:
        raise FoundPersonRejected(
            "outbound_consent_required",
            "Email first touch requires an explicit email opt-in",
        )
    try:
        normalized_phone = _normalize_phone(phone)
        normalized_email = _normalize_email(email)
    except ValueError as exc:
        raise FoundPersonRejected("found_person_identity_invalid", str(exc)) from exc
    if route == "sms" and not normalized_phone:
        raise FoundPersonRejected(
            "found_person_not_addressable",
            "SMS first touch requires a phone number",
        )
    if route == "email" and not normalized_email:
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
        channel=route,
        consent_basis=basis,
        idempotency_key=key,
    )


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
