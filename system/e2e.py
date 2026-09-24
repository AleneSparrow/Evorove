"""Walk one person through the four CRM tabs and report each stage.

Checks the board as the owner would see it: Cold -> In progress -> Offer made
-> Done, read from the CRM database (the staff board API needs a login and a
paid subscription; the rows behind it are the same). Cycle 1 must already
have run (run-e2e.sh does that). A stage that is never reached fails with the
roadmap step that owns it, so the output doubles as a to-do list.

Environment (defaults match docker-compose.yml, seen from inside `engine`):
  CRM_DATABASE_URL   postgresql://evorove:local_development_only@postgres:5432/crm
  ENGINE_URL         http://engine:8000
  CRM_URL            http://crm:8000
  E2E_BUSINESS_ID    acme-home-services
  E2E_PERSON_EMAIL   riley.e2e@example.com
  E2E_STAGE_TIMEOUT  seconds to wait for each stage (default 20)
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request

import psycopg

CRM_DATABASE_URL = os.getenv(
    "CRM_DATABASE_URL", "postgresql://evorove:local_development_only@postgres:5432/crm"
).replace("postgresql+psycopg://", "postgresql://")
ENGINE_URL = os.getenv("ENGINE_URL", "http://engine:8000").rstrip("/")
CRM_URL = os.getenv("CRM_URL", "http://crm:8000").rstrip("/")
BUSINESS_ID = os.getenv("E2E_BUSINESS_ID", "acme-home-services")
PERSON_EMAIL = os.getenv("E2E_PERSON_EMAIL", "riley.e2e@example.com")
STAGE_TIMEOUT = float(os.getenv("E2E_STAGE_TIMEOUT", "20"))

# Board tab value in board_people.tab -> (label the owner sees, step that makes it happen)
STAGES = (
    ("cold", "Cold", "cycle 1 -> CRM (evorove_lead run)"),
    ("in_work", "In progress", "Ш11 + Ш14: cycle 2 writes to the Cold person and reports the touch"),
    ("offer_sent", "Offer made", "Ш11 + Ш16: the reply continues the sale up to an offer"),
    ("done", "Done", "Ш23: booked hour (or Ш24 paid link) reported to CRM"),
)
ORDER = [tab for tab, _, _ in STAGES]


def healthy(base: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as response:
            return response.status == 200
    except OSError:
        return False


def current_tab(conn: psycopg.Connection) -> str | None:
    row = conn.execute(
        "SELECT tab FROM board_people WHERE business_id = %s AND lower(email) = lower(%s)",
        (BUSINESS_ID, PERSON_EMAIL),
    ).fetchone()
    return row[0] if row else None


def wait_for(conn: psycopg.Connection, tab: str) -> str | None:
    deadline = time.monotonic() + STAGE_TIMEOUT
    while True:
        seen = current_tab(conn)
        if seen is not None and seen in ORDER and ORDER.index(seen) >= ORDER.index(tab):
            return seen
        if time.monotonic() >= deadline:
            return seen
        time.sleep(1)


def main() -> int:
    failures = 0
    for name, base in (("engine", ENGINE_URL), ("crm", CRM_URL)):
        ok = healthy(base)
        print(f"{'PASS' if ok else 'FAIL'}  {name} /health  {base}")
        failures += not ok
    if failures:
        return 1

    with psycopg.connect(CRM_DATABASE_URL, autocommit=True) as conn:
        for tab, label, owner in STAGES:
            seen = wait_for(conn, tab)
            reached = seen is not None and seen in ORDER and ORDER.index(seen) >= ORDER.index(tab)
            if reached:
                print(f"PASS  {label}")
                continue
            print(f"FAIL  {label}  (board tab now: {seen or 'not on the board'}; owner: {owner})")
            failures += 1
            break
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
