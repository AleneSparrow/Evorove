"""Settings API round-trip for the owner-entered payment link (cycle 2 close).

The dashboard field is `payment_link` on the PUT body; it must persist to a new
DNA version and come back on GET. Anything that is not a bare http(s) URL is
rejected with 422 before it can reach the engine.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.config import Settings
from src.domain.tenancy import Business
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
BUSINESS = "biz-payment"
PAYMENT_LINK = "https://buy.stripe.com/test_4eC5928kK1MK2kE188"

# PUT body keys shared with the GET response (ApiModel forbids extras, so the
# body is built explicitly from a GET response rather than passed wholesale).
_SHARED_KEYS = (
    "name",
    "industry",
    "tone",
    "services",
    "service_zip_codes",
    "escalate_on_high_urgency",
    "escalate_on_emergency",
    "booking_enabled",
    "booking_timezone",
    "business_hours",
    "objection_responses",
    "compliance_disclaimer",
    "ai_disclosure_text",
    "payment_link",
)


@pytest.fixture
def environment(tmp_path: Path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'dna_api.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    application = create_app(settings=Settings(database_url=database_url, app_env="test"))
    with TestClient(application, raise_server_exceptions=False) as client:
        token = client.post(
            "/api/v1/auth/signup",
            json={"email": "payment-owner@example.com", "password": "correct horse battery"},
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["user_id"]
        _seed_business(factory, user_id)
        yield client, headers
    engine.dispose()


def _seed_business(factory, user_id: str) -> None:
    with (ROOT / "config" / "business_dna.example.json").open(encoding="utf-8") as file:
        configuration = json.load(file)
    configuration["business"]["id"] = BUSINESS
    with factory() as uow:
        uow.businesses.add(Business(
            BUSINESS,
            configuration["business"]["name"],
            NOW,
            NOW,
            plan="starter",
            subscription_status="active",
        ))
        uow.business_dna.add_version(BUSINESS, configuration)
        user = uow.staff_users.get(user_id)
        uow.staff_users.save(user.with_business(BUSINESS))
        uow.commit()


def _put_body(current: dict, **overrides) -> dict:
    body = {key: current[key] for key in _SHARED_KEYS}
    body.update(overrides)
    return body


def test_payment_link_round_trips_through_the_settings_api(environment) -> None:
    client, headers = environment

    current = client.get(f"/api/v1/businesses/{BUSINESS}/dna", headers=headers)
    assert current.status_code == 200
    assert current.json()["payment_link"] == ""

    # Settings only writes fixed-price quotes: a custom_quote service comes back
    # with quote_price null and must be given a price on save, same as the owner
    # entering one in the UI.
    services = [
        {**service, "quote_price": service["quote_price"] or "5500.00"}
        if service["commercial_path"] == "quote"
        else service
        for service in current.json()["services"]
    ]
    saved = client.put(
        f"/api/v1/businesses/{BUSINESS}/dna",
        headers=headers,
        json=_put_body(current.json(), services=services, payment_link=PAYMENT_LINK),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["payment_link"] == PAYMENT_LINK

    reread = client.get(f"/api/v1/businesses/{BUSINESS}/dna", headers=headers)
    assert reread.status_code == 200
    assert reread.json()["payment_link"] == PAYMENT_LINK
    assert reread.json()["version"] == saved.json()["version"]


def test_settings_api_rejects_non_http_payment_link(environment) -> None:
    client, headers = environment
    current = client.get(f"/api/v1/businesses/{BUSINESS}/dna", headers=headers).json()

    rejected = client.put(
        f"/api/v1/businesses/{BUSINESS}/dna",
        headers=headers,
        json=_put_body(current, payment_link="javascript:alert(1)"),
    )

    assert rejected.status_code == 422
    reread = client.get(f"/api/v1/businesses/{BUSINESS}/dna", headers=headers).json()
    assert reread["payment_link"] == ""
