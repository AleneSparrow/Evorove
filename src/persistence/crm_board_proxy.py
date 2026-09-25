"""The People tab of evorove.com reads and drives the CRM board.

The owner signs in and pays here, on evorove.com. The four-tab board (Cold /
In progress / Offer made / Done) is kept by the CRM service; this module
calls its internal routes with INTERNAL_TASK_SECRET so the board shows up as
one more tab of the same site, with the same login and the same business.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

LOGGER = logging.getLogger("uvicorn.error")
_TIMEOUT_SECONDS = 10


class CrmBoardError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class CrmBoardProxy:
    def __init__(self, crm_base_url: str | None, secret: str | None) -> None:
        self._base = (crm_base_url or "").rstrip("/") or None
        self._secret = secret

    @property
    def configured(self) -> bool:
        return bool(self._base and self._secret)

    def ensure_business(self, business_id: str, name: str) -> None:
        self._call("PUT", f"/businesses/{_q(business_id)}", {"name": name})

    def list_tab(self, business_id: str, tab: str) -> dict[str, Any]:
        return self._call("GET", f"/businesses/{_q(business_id)}/board?tab={_q(tab)}")

    def person(self, business_id: str, person_id: str) -> dict[str, Any]:
        return self._call("GET", f"/businesses/{_q(business_id)}/board/people/{_q(person_id)}")

    def command(self, business_id: str, person_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._call("POST", f"/businesses/{_q(business_id)}/board/people/{_q(person_id)}/commands", body)

    def start_search(self, business_id: str, site_url: str) -> dict[str, Any]:
        return self._call("POST", f"/businesses/{_q(business_id)}/board/search", {"site_url": site_url})

    def search_status(self, business_id: str) -> dict[str, Any]:
        return self._call("GET", f"/businesses/{_q(business_id)}/board/search")

    def _call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise CrmBoardError(503, "The People board is not connected yet.")
        request = urllib.request.Request(
            f"{self._base}/api/v1/internal{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            method=method,
            headers={"Content-Type": "application/json", "X-Internal-Task-Secret": self._secret or ""},
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            message = "The People board is unavailable right now."
            try:
                body = json.loads(exc.read() or b"{}")
                message = str((body.get("error") or {}).get("message") or body.get("message") or message)
            except (ValueError, AttributeError):
                pass
            LOGGER.warning("crm_board_proxy_http_error status=%s path=%s", exc.code, path.split("?")[0])
            raise CrmBoardError(exc.code if exc.code in (404, 422, 503) else 502, message) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            LOGGER.warning("crm_board_proxy_unreachable error=%s", type(exc).__name__)
            raise CrmBoardError(502, "The People board is unavailable right now.") from exc


def _q(value: str) -> str:
    return urllib.parse.quote(value, safe="")
