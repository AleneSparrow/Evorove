"""Calendar Settings endpoints: connect, callback, disconnect, tenant scoping."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.config import Settings
from src.domain.tenancy import Business
from src.persistence import calendar_service
from src.persistence.sqlalchemy_models import Base, CalendarConnectionRow
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
BUSINESS = "biz-calendar"
KEY = "k" * 40
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _fake_google(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, dict]:
    if url == TOKEN_URL:
        return 200, {"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600}
    return 500, {}


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(calendar_service, "post_google", _fake_google)
    database_url = f"sqlite+pysqlite:///{tmp_path / 'calendar_api.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    application = create_app(
        settings=Settings(
            database_url=database_url,
            app_env="test",
            google_calendar_client_id="cid",
            google_calendar_client_secret="csecret",
            account_security_encryption_key=KEY,
        )
    )
    with TestClient(application, raise_server_exceptions=False) as client:
        token = client.post(
            "/api/v1/auth/signup",
            json={"email": "calendar-owner@example.com", "password": "correct horse battery"},
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["user_id"]
        with (ROOT / "config" / "business_dna.example.json").open(encoding="utf-8") as file:
            configuration = json.load(file)
        configuration["business"]["id"] = BUSINESS
        with factory() as uow:
            uow.businesses.add(Business(
                BUSINESS, configuration["business"]["name"], NOW, NOW,
                plan="starter", subscription_status="active",
            ))
            uow.business_dna.add_version(BUSINESS, configuration)
            user = uow.staff_users.get(user_id)
            uow.staff_users.save(user.with_business(BUSINESS))
            uow.commit()
        yield client, headers, factory
    engine.dispose()


def test_status_connect_callback_and_disconnect(environment) -> None:
    client, headers, factory = environment
    base = f"/api/v1/businesses/{BUSINESS}/calendar"

    status = client.get(base, headers=headers)
    assert status.status_code == 200
    assert status.json()["enabled"] is True and status.json()["connected"] is False

    connect = client.post(
        f"{base}/connect",
        headers=headers,
        json={"redirect_uri": "https://app.example/app/settings?tab=calendar"},
    )
    assert connect.status_code == 200, connect.text
    state = connect.json()["auth_url"].split("state=")[1].split("&")[0]
    assert connect.json()["auth_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth")

    # A tampered state is rejected before any token exchange.
    tampered = client.post(f"{base}/callback", headers=headers, json={"state": "bogus.state", "code": "c"})
    assert tampered.status_code == 422

    done = client.post(f"{base}/callback", headers=headers, json={"state": state, "code": "one-time"})
    assert done.status_code == 200, done.text
    assert done.json()["connected"] is True

    with factory() as uow:
        row = uow.session.get(CalendarConnectionRow, BUSINESS)
        assert row is not None and row.encrypted_refresh_token != "rt-1"

    assert client.delete(base, headers=headers).status_code == 204
    assert client.get(base, headers=headers).json()["connected"] is False


def test_another_business_calendar_is_forbidden(environment) -> None:
    client, headers, _ = environment
    response = client.get("/api/v1/businesses/other-biz/calendar", headers=headers)
    assert response.status_code == 403


def test_connect_requires_https_redirect(environment) -> None:
    client, headers, _ = environment
    response = client.post(
        f"/api/v1/businesses/{BUSINESS}/calendar/connect",
        headers=headers,
        json={"redirect_uri": "http://insecure.example/settings"},
    )
    assert response.status_code == 422


def test_disabled_deployment_reports_enabled_false(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'off.db'}")
    Base.metadata.create_all(engine)
    application = create_app(settings=Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'off.db'}", app_env="test"))
    with TestClient(application, raise_server_exceptions=False) as client:
        token = client.post(
            "/api/v1/auth/signup",
            json={"email": "no-cal@example.com", "password": "correct horse battery"},
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_id = client.get("/api/v1/auth/me", headers=headers).json()["user_id"]
        factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
        with (ROOT / "config" / "business_dna.example.json").open(encoding="utf-8") as file:
            configuration = json.load(file)
        configuration["business"]["id"] = BUSINESS
        with factory() as uow:
            uow.businesses.add(Business(BUSINESS, configuration["business"]["name"], NOW, NOW))
            uow.business_dna.add_version(BUSINESS, configuration)
            user = uow.staff_users.get(user_id)
            uow.staff_users.save(user.with_business(BUSINESS))
            uow.commit()
        status = client.get(f"/api/v1/businesses/{BUSINESS}/calendar", headers=headers)
        assert status.json()["enabled"] is False
        connect = client.post(
            f"/api/v1/businesses/{BUSINESS}/calendar/connect",
            headers=headers,
            json={"redirect_uri": "https://app.example/settings"},
        )
        assert connect.status_code == 503
    engine.dispose()
