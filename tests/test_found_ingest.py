"""CRM journal Found ingest: cycle 2 writes. No people search. No live Twilio."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import (
    get_container,
    get_sms_service,
    get_unit_of_work_factory,
    get_whatsapp_mouth,
)
from src.api.errors import install_error_handlers
from src.api.routes import internal
from src.config import Settings
from src.domain.tenancy import Business
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
BUSINESS_ID = "acme-home-services"
SECRET = "internal-found-ingest-test-secret"
REASON = "Asked neighbors this week for help with a broken AC"


class FakeSms:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def is_suppressed(self, business_id: str, phone_number: str) -> bool:
        del business_id
        return False

    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None:
        del business_id
        self.sent.append((to_number, body))
        return "SM_found"


class FakeWhatsApp:
    def __init__(self, *, configured: bool = True) -> None:
        self.sent: list[tuple[str, str]] = []
        self.configured = configured

    def is_suppressed(self, business_id: str, phone_number: str) -> bool:
        del business_id, phone_number
        return False

    def send_outbound(self, business_id: str, *, to_number: str, body: str) -> str | None:
        del business_id
        if not self.configured:
            return None
        self.sent.append((to_number, body))
        return "WA_found"


def _dna(business_id: str) -> dict:
    with (ROOT / "config" / "business_dna.example.json").open(encoding="utf-8") as file:
        configuration = json.load(file)
    configuration["business"]["id"] = business_id
    return configuration


def _client(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'found-ingest.db'}")
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    with factory() as uow:
        uow.businesses.add(Business(BUSINESS_ID, BUSINESS_ID, NOW, NOW))
        uow.business_dna.add_version(BUSINESS_ID, _dna(BUSINESS_ID))
        uow.commit()
    sms = FakeSms()
    whatsapp = FakeWhatsApp()
    container = SimpleNamespace(
        settings=Settings(
            database_url=f"sqlite+pysqlite:///{tmp_path / 'found-ingest.db'}",
            app_env="test",
            internal_task_secret=SECRET,
        ),
        unit_of_work_factory=factory,
        sales_turn_analyzer=None,
        sales_response_generator=None,
    )
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(internal.router)
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_unit_of_work_factory] = lambda: factory
    app.dependency_overrides[get_sms_service] = lambda: sms
    app.dependency_overrides[get_whatsapp_mouth] = lambda: whatsapp
    return app, engine, sms, whatsapp


def _card(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "schema_version": "1",
        "person_id": "ppl_ada_found_01",
        "reason": REASON,
        "source": "open-web-neighbor-post",
        "channel": "sms",
        "preferred_channel": "sms",
        "consent_basis": "prior_express_written",
        "identity": {"name": "Ada", "phone": "+15551234567"},
    }
    payload.update(overrides)
    return payload


def test_crm_found_ingest_writes_greet_without_owner(tmp_path) -> None:
    app, engine, sms, _wa = _client(tmp_path)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/found",
                json=_card(),
                headers={"X-Internal-Task-Secret": SECRET},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["duplicate"] is False
        assert body["delivered"] is True
        lowered = body["message_text"].casefold()
        assert "evorove for acme home services" in lowered
        assert "you reached out" not in lowered
        assert sms.sent and sms.sent[0][0] == "+15551234567"
    finally:
        engine.dispose()


def test_crm_found_ingest_is_idempotent(tmp_path) -> None:
    app, engine, sms, _wa = _client(tmp_path)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            first = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/found",
                json=_card(),
                headers={"X-Internal-Task-Secret": SECRET},
            )
            second = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/found",
                json=_card(),
                headers={"X-Internal-Task-Secret": SECRET},
            )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["duplicate"] is True
        assert second.json()["case_id"] == first.json()["case_id"]
        assert len(sms.sent) == 1
    finally:
        engine.dispose()


def test_crm_found_ingest_rejects_a_dump_without_reason(tmp_path) -> None:
    app, engine, sms, _wa = _client(tmp_path)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/found",
                json=_card(reason="Ada"),
                headers={"X-Internal-Task-Secret": SECRET},
            )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "found_person_reason_required"
        assert sms.sent == []
    finally:
        engine.dispose()


def test_whatsapp_alone_sends_on_evorove_mouth(tmp_path) -> None:
    app, engine, sms, whatsapp = _client(tmp_path)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/found",
                json=_card(
                    channel=None,
                    preferred_channel="whatsapp",
                    consent_basis="whatsapp_opt_in",
                    identity={
                        "name": "Ada",
                        "phone": "+15551234567",
                        "messenger_id": "wa:15551234567",
                    },
                ),
                headers={"X-Internal-Task-Secret": SECRET},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["delivered"] is True
        assert "evorove for acme home services" in body["message_text"].casefold()
        assert sms.sent == []
        assert whatsapp.sent and whatsapp.sent[0][0] == "+15551234567"
    finally:
        engine.dispose()


def test_crm_found_ingest_stores_stated_portrait_labels(tmp_path) -> None:
    app, engine, sms, _wa = _client(tmp_path)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/found",
                json=_card(
                    identity={
                        "name": "Ada",
                        "phone": "+15551234567",
                        "gender": "Woman",
                        "region": "Illinois",
                    },
                ),
                headers={"X-Internal-Task-Secret": SECRET},
            )
        assert response.status_code == 200, response.text
        lead_id = response.json()["lead_id"]
        factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
        with factory() as uow:
            lead = uow.leads.get(BUSINESS_ID, lead_id)
            assert lead is not None
            assert lead.attributes["gender"] == "Woman"
            assert lead.attributes["region"] == "Illinois"
        assert sms.sent
    finally:
        engine.dispose()


def test_found_ingest_requires_the_internal_secret(tmp_path) -> None:
    app, engine, sms, _wa = _client(tmp_path)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/api/v1/internal/businesses/{BUSINESS_ID}/found",
                json=_card(),
            )
        assert response.status_code == 401
        assert sms.sent == []
    finally:
        engine.dispose()
