"""Report cycle-2 journal touches and the cycle-3 hot-lead exit.

Journal: Found (CRM) → Opened → In play → Hot. HTTP is outbox-backed.
Ready-to-book POSTs `/hot-leads` (C2-6). Cycle 2 does not send a calendar slot.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import timedelta
from typing import Any, Protocol
from uuid import uuid4

from dataclasses import replace
from sqlalchemy import select

from src.domain.models import ProcessCase, utc_now
from src.domain.sales import SalesMove, SalesMoveDecision, CustomerSalesProfile
from src.persistence.sqlalchemy_models import IntegrationOutboxRow

PERSON_ID_PREFIX = "ppl_"
LOGGER = logging.getLogger("uvicorn.error")
CRM_TOUCH_KIND = "crm_touch"
CRM_HOT_LEAD_KIND = "crm_hot_lead"
JOURNAL_OPENED = "opened"
JOURNAL_IN_PLAY = "in_play"
JOURNAL_HOT = "hot"
JOURNAL_HUMAN = "human"
_MAX_ATTEMPTS = 8
_BACKOFF = timedelta(minutes=5)


class CrmTouchPublisher(Protocol):
    def publish(self, business_id: str, payload: dict[str, Any]) -> None: ...

    def publish_hot_lead(self, business_id: str, payload: dict[str, Any]) -> None: ...

    def deliver_due(self, *, limit: int = 50) -> dict[str, int]: ...


class NullCrmTouchPublisher:
    def publish(self, business_id: str, payload: dict[str, Any]) -> None:
        return None

    def publish_hot_lead(self, business_id: str, payload: dict[str, Any]) -> None:
        return None

    def deliver_due(self, *, limit: int = 50) -> dict[str, int]:
        del limit
        return {"attempted": 0, "sent": 0, "failed": 0}


class RecordingCrmTouchPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []
        self.hot_leads: list[tuple[str, dict[str, Any]]] = []

    def publish(self, business_id: str, payload: dict[str, Any]) -> None:
        self.published.append((business_id, payload))

    def publish_hot_lead(self, business_id: str, payload: dict[str, Any]) -> None:
        self.hot_leads.append((business_id, payload))

    def deliver_due(self, *, limit: int = 50) -> dict[str, int]:
        del limit
        return {"attempted": 0, "sent": 0, "failed": 0}


class HttpCrmTouchPublisher:
    def __init__(self, base_url: str, secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret

    def publish(self, business_id: str, payload: dict[str, Any]) -> None:
        self.post_touch(business_id, payload)

    def post_hot_lead(self, business_id: str, payload: dict[str, Any]) -> bool:
        return self._post(f"/api/v1/internal/businesses/{business_id}/hot-leads", payload)

    def publish_hot_lead(self, business_id: str, payload: dict[str, Any]) -> None:
        self.post_hot_lead(business_id, payload)

    def deliver_due(self, *, limit: int = 50) -> dict[str, int]:
        del limit
        return {"attempted": 0, "sent": 0, "failed": 0}

    def post_touch(self, business_id: str, payload: dict[str, Any]) -> bool:
        return self._post(f"/api/v1/internal/businesses/{business_id}/lead-touches", payload)

    def _post(self, path: str, payload: dict[str, Any]) -> bool:
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Internal-Task-Secret": self._secret,
            },
        )
        try:
            urllib.request.urlopen(request, timeout=5).close()
            return True
        except (urllib.error.URLError, TimeoutError, OSError):
            return False


class OutboxCrmTouchPublisher:
    """Write the journal event first, then POST. Sale does not wait on CRM."""

    def __init__(self, unit_of_work_factory: Any, base_url: str, secret: str) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self._http = HttpCrmTouchPublisher(base_url, secret)

    def publish(self, business_id: str, payload: dict[str, Any]) -> None:
        self._enqueue(
            business_id,
            outbox_id=str(payload.get("touch_id") or uuid4())[:128],
            kind=CRM_TOUCH_KIND,
            payload=payload,
        )

    def publish_hot_lead(self, business_id: str, payload: dict[str, Any]) -> None:
        handoff_id = str(payload.get("handoff_id") or uuid4())
        self._enqueue(
            business_id,
            outbox_id=f"hot:{handoff_id}"[:128],
            kind=CRM_HOT_LEAD_KIND,
            payload=payload,
        )

    def _enqueue(
        self,
        business_id: str,
        *,
        outbox_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> None:
        now = utc_now()
        try:
            with self.unit_of_work_factory() as uow:
                session = getattr(uow, "session", None)
                if session is None:
                    self._deliver_payload(kind, business_id, payload)
                    return
                existing = session.get(IntegrationOutboxRow, outbox_id)
                if existing is None:
                    session.add(
                        IntegrationOutboxRow(
                            id=outbox_id,
                            business_id=business_id,
                            kind=kind,
                            payload=payload,
                            status="PENDING",
                            attempt_count=0,
                            next_attempt_at=now,
                            last_error=None,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    uow.commit()
                elif existing.status != "PENDING":
                    return
            self.deliver_one(outbox_id)
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "crm_outbox_enqueue_failed business_id=%s kind=%s outbox_id=%s",
                business_id,
                kind,
                outbox_id,
            )

    def deliver_due(self, *, limit: int = 50) -> dict[str, int]:
        now = utc_now()
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return {"attempted": 0, "sent": 0, "failed": 0}
            rows = session.scalars(
                select(IntegrationOutboxRow)
                .where(
                    IntegrationOutboxRow.status == "PENDING",
                    IntegrationOutboxRow.kind.in_((CRM_TOUCH_KIND, CRM_HOT_LEAD_KIND)),
                    IntegrationOutboxRow.next_attempt_at <= now,
                )
                .order_by(IntegrationOutboxRow.created_at.asc())
                .limit(limit)
            ).all()
            ids = [row.id for row in rows]
        attempted = sent = failed = 0
        for outbox_id in ids:
            attempted += 1
            if self.deliver_one(outbox_id):
                sent += 1
            else:
                failed += 1
        return {"attempted": attempted, "sent": sent, "failed": failed}

    def deliver_one(self, outbox_id: str) -> bool:
        with self.unit_of_work_factory() as uow:
            session = getattr(uow, "session", None)
            if session is None:
                return False
            row = session.get(IntegrationOutboxRow, outbox_id)
            if row is None or row.status != "PENDING":
                return row is not None and row.status == "SENT"
            payload = dict(row.payload)
            now = utc_now()
            delivered = self._deliver_payload(row.kind, row.business_id, payload)
            row.attempt_count += 1
            row.updated_at = now
            if delivered:
                row.status = "SENT"
                row.last_error = None
                uow.commit()
                return True
            if row.attempt_count >= _MAX_ATTEMPTS:
                row.status = "FAILED"
                row.last_error = "delivery_exhausted"
            else:
                row.next_attempt_at = now + (_BACKOFF * row.attempt_count)
                row.last_error = "delivery_failed"
            uow.commit()
            return False

    def _deliver_payload(self, kind: str, business_id: str, payload: dict[str, Any]) -> bool:
        if kind == CRM_HOT_LEAD_KIND:
            return self._http.post_hot_lead(business_id, payload)
        return self._http.post_touch(business_id, payload)


def publisher_from_env() -> CrmTouchPublisher:
    return publisher_from_settings()


def publisher_from_settings(
    settings: Any | None = None,
    unit_of_work_factory: Any | None = None,
) -> CrmTouchPublisher:
    if settings is None:
        base = (os.getenv("CRM_BASE_URL") or "").strip().rstrip("/")
        secret = os.getenv("INTERNAL_TASK_SECRET") or ""
    else:
        base = (getattr(settings, "crm_base_url", None) or "").strip().rstrip("/")
        secret = getattr(settings, "internal_task_secret", None) or ""
    if not (base and secret):
        return NullCrmTouchPublisher()
    if unit_of_work_factory is not None:
        return OutboxCrmTouchPublisher(unit_of_work_factory, base, secret)
    return HttpCrmTouchPublisher(base, secret)


def stable_person_id(
    business_id: str,
    *,
    phone: str | None = None,
    email: str | None = None,
    person_id: str | None = None,
) -> str | None:
    existing = (person_id or "").strip()
    if existing.startswith(PERSON_ID_PREFIX):
        return existing
    key = (phone or "").strip() or (email or "").strip().casefold()
    if not key:
        return None
    digest = hashlib.sha256(f"{business_id}\n{key}".encode("utf-8")).hexdigest()[:32]
    return f"{PERSON_ID_PREFIX}{digest}"


def ensure_person_id(case: ProcessCase) -> str | None:
    stored = case.lead.attributes.get("person_id")
    existing = stored if isinstance(stored, str) else None
    person_id = stable_person_id(
        case.business_id, phone=case.lead.phone, email=case.lead.email, person_id=existing
    )
    if person_id and person_id != existing:
        attributes = dict(case.lead.attributes)
        attributes["person_id"] = person_id
        case.update_lead(replace(case.lead, attributes=attributes))
    return person_id


def _dialogue_line(text: str | None) -> str:
    """Bound a spoken line for the CRM card. The board shows the dialogue, not a status word."""

    cleaned = " ".join((text or "").split())
    return cleaned[:2000]


def touch_payloads_for_turn(
    *,
    case: ProcessCase,
    previous: CustomerSalesProfile,
    decision: SalesMoveDecision,
    source_message_id: str,
    summary: str,
    customer_text: str | None = None,
    engine_text: str | None = None,
) -> list[dict[str, Any]]:
    person_id = ensure_person_id(case)
    if person_id is None:
        return []
    kinds: list[str] = []
    if decision.move is SalesMove.HANDOFF_TO_HUMAN:
        kinds.append(JOURNAL_HUMAN)
    elif decision.move is SalesMove.OFFER_BOOKING_SLOTS:
        kinds.append(JOURNAL_HOT)
    elif previous.last_move is None:
        kinds.append(JOURNAL_OPENED)
    else:
        kinds.append(JOURNAL_IN_PLAY)
    payloads = []
    for kind in kinds:
        payloads.append(
            {
                "schema_version": "1",
                "touch_id": f"cycle2:{kind}:{source_message_id}"[:128],
                "person_id": person_id,
                "cycle": 2,
                "kind": kind,
                "source": "evorove",
                "summary": summary[:500],
                "identity": {
                    "name": case.lead.name,
                    "phone": case.lead.phone,
                    "email": case.lead.email,
                },
                "payload": {
                    "case_id": case.case_id,
                    "move": decision.move.value,
                    "source_message_id": source_message_id,
                    "customer_text": _dialogue_line(customer_text),
                    "engine_text": _dialogue_line(engine_text),
                },
            }
        )
    return payloads
