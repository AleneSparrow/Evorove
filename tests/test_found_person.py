"""CRM Found card contract for cycle 2: send mouths include Evorove WhatsApp."""

import pytest

from src.domain.found_person import (
    ALLOWED_OUTBOUND_CHANNELS,
    DECLARED_PREFERRED_CHANNELS,
    FoundPersonRejected,
    parse_crm_found_card,
    parse_found_person,
)

REASON = "Asked neighbors this week for help with a broken AC"


def test_send_mouths_include_evorove_whatsapp() -> None:
    assert ALLOWED_OUTBOUND_CHANNELS == frozenset({"sms", "email", "whatsapp"})
    assert DECLARED_PREFERRED_CHANNELS == frozenset({"sms", "email", "whatsapp"})


def test_crm_found_payload_keeps_preferred_whatsapp_and_sends_sms() -> None:
    person = parse_found_person(
        idempotency_key="found-ada-ac-001",
        reason=REASON,
        source="crm-journal-found",
        channel="sms",
        consent_basis="prior_express_written",
        name="Ada",
        phone="+15551234567",
        person_id="crm-found-ada-001",
        preferred_channel="whatsapp",
        messenger_id="wa:15551234567",
    )
    assert person.channel == "sms"
    assert person.preferred_channel == "whatsapp"
    assert person.person_id == "crm-found-ada-001"
    assert person.messenger_id == "wa:15551234567"
    assert person.address == "+15551234567"


def test_preferred_sms_can_fill_missing_send_channel() -> None:
    person = parse_found_person(
        idempotency_key="found-ada-ac-002",
        reason=REASON,
        source="crm-journal-found",
        channel=None,
        consent_basis="prior_express_written",
        phone="+15551234567",
        preferred_channel="sms",
    )
    assert person.channel == "sms"
    assert person.preferred_channel == "sms"


def test_preferred_whatsapp_alone_sends_whatsapp_with_opt_in() -> None:
    person = parse_found_person(
        idempotency_key="found-ada-ac-003",
        reason=REASON,
        source="crm-journal-found",
        channel=None,
        consent_basis="whatsapp_opt_in",
        phone="+15551234567",
        preferred_channel="whatsapp",
        messenger_id="wa:15551234567",
    )
    assert person.channel == "whatsapp"
    assert person.consent_basis == "whatsapp_opt_in"
    assert person.address == "+15551234567"


def test_sms_consent_does_not_authorize_whatsapp() -> None:
    with pytest.raises(FoundPersonRejected) as caught:
        parse_found_person(
            idempotency_key="found-ada-ac-003b",
            reason=REASON,
            source="crm-journal-found",
            channel=None,
            consent_basis="prior_express_written",
            phone="+15551234567",
            preferred_channel="whatsapp",
        )
    assert caught.value.code == "outbound_consent_required"


def test_instagram_is_not_a_send_mouth() -> None:
    with pytest.raises(FoundPersonRejected) as caught:
        parse_found_person(
            idempotency_key="found-ada-ac-004b",
            reason=REASON,
            source="crm-journal-found",
            channel="instagram",
            consent_basis="prior_express_written",
            phone="+15551234567",
        )
    assert caught.value.code == "outbound_channel_invalid"


def test_instagram_is_not_a_mouth() -> None:
    with pytest.raises(FoundPersonRejected) as caught:
        parse_found_person(
            idempotency_key="found-ada-ac-004",
            reason=REASON,
            source="crm-journal-found",
            channel="sms",
            consent_basis="prior_express_written",
            phone="+15551234567",
            preferred_channel="instagram",
        )
    assert caught.value.code == "preferred_channel_invalid"


def test_missing_reason_is_still_rejected() -> None:
    with pytest.raises(FoundPersonRejected) as caught:
        parse_found_person(
            idempotency_key="found-ada-ac-005",
            reason="Ada",
            source="crm-journal-found",
            channel="sms",
            consent_basis="prior_express_written",
            phone="+15551234567",
        )
    assert caught.value.code == "found_person_reason_required"


def test_crm_journal_card_requires_person_id() -> None:
    with pytest.raises(FoundPersonRejected) as caught:
        parse_crm_found_card({
            "reason": REASON,
            "source": "open-web-neighbor-post",
            "channel": "sms",
            "consent_basis": "prior_express_written",
            "identity": {"phone": "+15551234567"},
        })
    assert caught.value.code == "found_person_id_required"


def test_crm_journal_card_maps_nested_identity() -> None:
    person = parse_crm_found_card({
        "person_id": "ppl_ada_found_01",
        "reason": REASON,
        "source": "open-web-neighbor-post",
        "channel": "sms",
        "preferred_channel": "whatsapp",
        "consent_basis": "prior_express_written",
        "identity": {
            "name": "Ada",
            "phone": "+15551234567",
            "messenger_id": "wa:15551234567",
        },
    })
    assert person.idempotency_key == "found:ppl_ada_found_01"
    assert person.channel == "sms"
    assert person.preferred_channel == "whatsapp"
    assert person.messenger_id == "wa:15551234567"
    assert person.address == "+15551234567"
    assert person.gender is None
    assert person.region is None


def test_crm_journal_card_keeps_stated_gender_and_region_without_guessing() -> None:
    person = parse_crm_found_card({
        "person_id": "ppl_ada_found_02",
        "reason": REASON,
        "source": "open-web-neighbor-post",
        "channel": "sms",
        "consent_basis": "prior_express_written",
        "identity": {
            "name": "Ada",
            "phone": "+15551234567",
            "gender": "Woman",
            "region": "Illinois",
        },
    })
    assert person.gender == "Woman"
    assert person.region == "Illinois"


def test_crm_journal_card_does_not_invent_gender_from_a_name() -> None:
    person = parse_crm_found_card({
        "person_id": "ppl_ada_found_03",
        "reason": REASON,
        "source": "open-web-neighbor-post",
        "channel": "sms",
        "consent_basis": "prior_express_written",
        "identity": {"name": "Ada", "phone": "+15551234567"},
    })
    assert person.gender is None
    assert person.region is None
