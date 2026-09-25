"""evorove.com's People tab: same login and business, board kept by the CRM."""

import io
import json
import urllib.error
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.config import Settings
from src.domain.models import utc_now
from src.domain.tenancy import Business
from src.persistence import crm_board_proxy
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine
from tests.test_dashboard import link_business, signup_and_login

SECRET = "board-secret"


class FakeCrm:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self.fail: Exception | None = None

    def __call__(self, request, timeout=None):
        body = json.loads(request.data) if request.data else None
        self.calls.append((request.get_method(), request.full_url, body))
        assert request.get_header("X-internal-task-secret") == SECRET
        if self.fail is not None:
            raise self.fail
        if request.full_url.endswith("/board?tab=cold"):
            return io.BytesIO(json.dumps({"tab": "cold", "people": [{"person_id": "person-1"}]}).encode())
        return io.BytesIO(json.dumps({"ok": True}).encode())


def _world(tmp_path: Path, monkeypatch, status: str = "active"):
    fake = FakeCrm()
    monkeypatch.setattr(crm_board_proxy.urllib.request, "urlopen", fake)
    database_url = f"sqlite+pysqlite:///{tmp_path / 'tab.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    now = utc_now()
    with factory() as uow:
        uow.businesses.add(Business("biz-1", "Evorove", now, now, plan="starter", subscription_status=status))
        uow.commit()
    app = create_app(settings=Settings(database_url=database_url, app_env="test", internal_task_secret=SECRET,
                                       crm_base_url="https://crm.internal"))
    return app, factory, fake, engine


def _owner(client, factory):
    token = signup_and_login(client, "alena@example.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    link_business(factory, business_id="biz-1", user_id=me["user_id"])
    return {"Authorization": f"Bearer {token}"}


def test_people_tab_uses_the_site_login_and_the_crm_board(tmp_path, monkeypatch) -> None:
    app, factory, fake, engine = _world(tmp_path, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        headers = _owner(client, factory)
        assert client.get("/api/v1/businesses/biz-1/board?tab=cold").status_code == 401
        listed = client.get("/api/v1/businesses/biz-1/board?tab=cold", headers=headers)
        assert listed.status_code == 200 and listed.json()["people"][0]["person_id"] == "person-1"
        assert fake.calls[0] == ("PUT", "https://crm.internal/api/v1/internal/businesses/biz-1", {"name": "Evorove"})
        client.post("/api/v1/businesses/biz-1/board/people/person-1/commands", json={"action": "discard"}, headers=headers)
        assert fake.calls[-1][2] == {"action": "discard", "approved_by": "alena@example.com"}
        client.post("/api/v1/businesses/biz-1/board/search", json={"site_url": "https://acme.com"}, headers=headers)
        assert fake.calls[-1][1].endswith("/businesses/biz-1/board/search")
        fake.fail = urllib.error.URLError("down")
        down = client.get("/api/v1/businesses/biz-1/board/people/person-1", headers=headers)
        assert down.status_code == 502 and "unavailable" in down.text
    engine.dispose()


def test_people_tab_follows_the_site_subscription(tmp_path, monkeypatch) -> None:
    app, factory, fake, engine = _world(tmp_path, monkeypatch, status="incomplete")
    with TestClient(app, raise_server_exceptions=False) as client:
        headers = _owner(client, factory)
        assert client.get("/api/v1/businesses/biz-1/board", headers=headers).status_code == 402
        assert fake.calls == []
    engine.dispose()
