"""Replies to cold email continue the sales dialogue (roadmap step 16)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.app import create_app
from src.api.dependencies import build_email_inbox_service
from src.config import Settings
from src.persistence import crm_board_service, email_outreach_service
from src.persistence.email_inbox_service import InboundEmail, is_opt_out, parse_email, reply_text
from src.persistence.sqlalchemy_models import (
    Base,
    ConversationMessageRow,
    EmailConnectionRow,
    IntegrationOutboxRow,
)
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine
from tests.test_conversations import CountingExtractor, seed
from tests.test_email_outreach import KEY, FakeSmtp, _settings

SECRET = "board-secret"
CRM = "https://crm.example"
PUBLIC = "https://api.example"
PERSON = "person-0001"
PROSPECT = "owner@shop.example"


class FakeInbox:
    def __init__(self) -> None:
        self.messages: list[InboundEmail] = []
        self.seen_cursor: list[int | None] = []

    def __call__(self, target, last_uid):
        self.seen_cursor.append(last_uid)
        if last_uid is None:
            return [], 100
        new = [message for message in self.messages if message.uid > last_uid]
        return new, (new[-1].uid if new else last_uid)


def _reply(uid: int, text: str, sender: str = PROSPECT, **extra) -> InboundEmail:
    return InboundEmail(
        uid=uid, message_id=f"<r{uid}@shop.example>", from_address=sender,
        subject="Re: Quick question for Dana", text=text, **extra,
    )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    posts: list[dict] = []
    monkeypatch.setattr(crm_board_service, "post_internal_json", lambda url, secret, payload: (posts.append(payload) or (True, None)))
    monkeypatch.setattr(email_outreach_service, "in_business_quiet_hours", lambda now, dna: False)
    smtp = FakeSmtp()
    monkeypatch.setattr(email_outreach_service, "smtp_send", smtp)
    database_url = f"sqlite+pysqlite:///{tmp_path / 'inbox.db'}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = SQLAlchemyUnitOfWork.factory_for_engine(engine)
    seed(factory, "tenant-a")
    app = create_app(
        settings=Settings(
            database_url=database_url, app_env="test", internal_task_secret=SECRET, crm_base_url=CRM,
            account_security_encryption_key=KEY, public_api_base_url=PUBLIC,
            public_chat_rate_limit_requests=100,
        ),
        intent_extractor=CountingExtractor(),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        container = app.state.container
        inbox_service = build_email_inbox_service(container)
        fake = FakeInbox()
        inbox_service._fetcher = fake
        email = inbox_service._email
        email._sender = smtp
        outreach = inbox_service._outreach
        email.connect("tenant-a", _settings())
        outreach.assign_cold(
            "tenant-a", person_id=PERSON, email=PROSPECT, phone=None, name="Dana Smith",
            reason="Posted that weekend calls go to voicemail", reason_source="forum",
        )
        outreach.approve("tenant-a", PERSON, approved_by="alena@example.com")
        assert inbox_service.poll("tenant-a") == {"received": 0, "replied": 0, "opted_out": 0}  # sets the baseline
        smtp.sent.clear()
        posts.clear()
        yield client, inbox_service, fake, smtp, posts, factory
    engine.dispose()


def test_reply_continues_the_dialogue_in_the_same_thread(world) -> None:
    client, inbox, fake, smtp, posts, factory = world
    fake.messages.append(_reply(101, "Yes, tell me more. How would it work for my AC repair shop?\n\nOn Mon, Alena wrote:\n> Hi Dana"))
    assert inbox.poll("tenant-a")["replied"] == 1

    (_, answer), = smtp.sent
    assert answer["To"] == PROSPECT and answer["Subject"] == "Re: Quick question for Dana"
    assert answer["In-Reply-To"] == "<r101@shop.example>"
    assert "100 Main St, Springfield, IL 62701" in answer.get_content()
    assert answer["List-Unsubscribe"]

    with factory() as uow:
        texts = [row.text for row in uow.session.scalars(select(ConversationMessageRow).order_by(ConversationMessageRow.sequence_number)).all()]
    assert texts[0].startswith("Quick question for Dana")  # the engine saw what we wrote first
    assert texts[1].startswith("Yes, tell me more") and "> Hi Dana" not in texts[1]

    messages = [p for p in posts if p["kind"] == "message"]
    assert [m["payload"]["direction"] for m in messages] == ["inbound", "outbound"]
    assert {m.get("person_id") for m in posts} == {PERSON}  # same CRM card as cycle 1

    assert inbox.poll("tenant-a")["received"] == 0  # the cursor moved; nothing handled twice
    assert len(smtp.sent) == 1


def test_no_reply_unsubscribes(world) -> None:
    _, inbox, fake, smtp, posts, _ = world
    fake.messages.append(_reply(101, "No thanks."))
    assert inbox.poll("tenant-a")["opted_out"] == 1
    assert smtp.sent == []
    assert inbox._email.is_suppressed("tenant-a", email=PROSPECT)
    assert [p["kind"] for p in posts] == ["stopped"]


def test_strangers_auto_replies_and_own_mail_are_ignored(world) -> None:
    _, inbox, fake, smtp, posts, factory = world
    fake.messages += [
        _reply(101, "Buy our SEO services", sender="spam@else.example"),
        _reply(102, "I am out of the office until Monday", automatic=True),
        _reply(103, "copy", sender="alena@getevorove.com"),
    ]
    assert inbox.poll("tenant-a") == {"received": 0, "replied": 0, "opted_out": 0}
    assert smtp.sent == [] and posts == []
    with factory() as uow:
        assert uow.session.get(EmailConnectionRow, "tenant-a").imap_last_uid == 103


def test_paused_person_is_shown_but_not_answered(world) -> None:
    _, inbox, fake, smtp, posts, _ = world
    assert inbox._outreach.stop("tenant-a", email=PROSPECT, phone=None) == 1  # board pause after the first email
    fake.messages.append(_reply(101, "Can you call me?"))
    inbox.poll("tenant-a")
    assert smtp.sent == []
    assert [(p["kind"], p["summary"]) for p in posts] == [("message", "Customer: Can you call me?")]


def test_owner_takeover_stops_auto_answers(world) -> None:
    client, inbox, fake, smtp, posts, _ = world
    fake.messages.append(_reply(101, "Tell me more"))
    inbox.poll("tenant-a")
    smtp.sent.clear()
    body = {"command_id": "t1", "action": "takeover", "email": PROSPECT, "payload": {}}
    assert client.post("/api/v1/internal/businesses/tenant-a/lead-commands", json=body,
                       headers={"X-Internal-Task-Secret": SECRET}).status_code == 200
    fake.messages.append(_reply(102, "Hello? When can we talk?"))
    inbox.poll("tenant-a")
    assert smtp.sent == []


def test_failure_keeps_the_cursor_for_a_retry(world, monkeypatch: pytest.MonkeyPatch) -> None:
    _, inbox, fake, smtp, _, factory = world
    fake.messages.append(_reply(101, "Tell me more"))
    monkeypatch.setattr(inbox._intake, "receive", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ai down")))
    inbox.poll("tenant-a")
    with factory() as uow:
        assert uow.session.get(EmailConnectionRow, "tenant-a").imap_last_uid == 100
    monkeypatch.undo()
    monkeypatch.setattr(email_outreach_service, "in_business_quiet_hours", lambda now, dna: False)
    assert inbox.poll("tenant-a")["replied"] == 1


def test_sweep_reads_the_inbox(world, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, fake, smtp, _, _ = world
    import src.persistence.email_inbox_service as module

    monkeypatch.setattr(module, "imap_fetch", fake)  # the sweep builds its own service
    fake.messages.append(_reply(101, "Interested, what does it cost?"))
    swept = client.post("/api/v1/internal/integrations/deliver", headers={"X-Internal-Task-Secret": SECRET})
    assert swept.status_code == 200
    assert len(smtp.sent) == 1


def test_parsing_and_opt_out_rules() -> None:
    raw = (
        b"From: Dana <Owner@Shop.example>\r\nTo: alena@getevorove.com\r\nSubject: Re: Quick question\r\n"
        b"Message-ID: <abc@shop.example>\r\nIn-Reply-To: <x@getevorove.com>\r\nAuto-Submitted: auto-replied\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\nThanks!\r\n"
    )
    parsed = parse_email(7, raw)
    assert parsed.from_address == "owner@shop.example" and parsed.automatic is True
    assert parsed.in_reply_to == "<x@getevorove.com>" and parsed.text.strip() == "Thanks!"
    assert reply_text("Sure.\n-----Original Message-----\nold") == "Sure."
    for text in ("no", "No thanks!", "Please remove me from your list", "not interested, sorry", "UNSUBSCRIBE"):
        assert is_opt_out(text), text
    for text in ("Yes please", "Know more? No problem, send details", "How does it work?"):
        assert not is_opt_out(text), text
