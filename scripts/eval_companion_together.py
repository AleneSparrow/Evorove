"""Companion eval against a live Together dedicated endpoint.

Reads TOGETHER_API_KEY from the environment ONLY -- never accept it as a
CLI argument (would land in shell history / process list) and never print
it or the raw Authorization header. The agent that wrote this script does
not run it and does not see the key: the owner exports the variable in
their own terminal and runs this themselves.

Does not touch AI_PROVIDER, does not approve cards. Uses only the
standard library (urllib) -- no extra pip install needed.

Usage:
    export TOGETHER_API_KEY=...        # in YOUR terminal, not shared
    python3 scripts/eval_companion_together.py --model alenesparrowvn-365f/evorove-eval
    python3 scripts/eval_companion_together.py --model ... --seed-only   # fast smoke check first
    python3 scripts/eval_companion_together.py --model ... --limit 40    # cap cost
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _ssl_context() -> ssl.SSLContext:
    """Default context, but pointed at certifi's CA bundle when available.

    Some macOS Python installs (notably python.org's installer) ship with
    no root certificates wired up until the separate "Install
    Certificates.command" is run -- every HTTPS request then fails with
    CERTIFICATE_VERIFY_FAILED regardless of the target being perfectly
    reachable. Falls back to ssl.create_default_context() unchanged if
    certifi isn't installed; verification stays on either way -- this is
    not a workaround that disables cert checking.
    """

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.companion_corpus.lora_eval import (
    breakdown_by_move_and_objection,
    load_eval_rows,
    load_seed_rows,
    prompt_messages,
    score_row,
)
from src.companion_corpus.sft_export import STEP1

TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"


def call_together(model: str, messages: list[dict[str, str]], api_key: str, max_tokens: int, retries: int = 3) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOGETHER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    context = _ssl_context()
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60, context=context) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                return payload["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except Exception as exc:  # network hiccup -- retry
            last_error = exc
            time.sleep(1 * (attempt + 1))
    raise RuntimeError(f"Together call failed after {retries} attempts: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="Together endpoint model string, e.g. yourorg/evorove-eval")
    parser.add_argument("--seed-only", action="store_true", help="Score only the small hand-authored fixtures (fast, cheap smoke check).")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of rows scored, in file order (cost control).")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports" / f"companion-together-eval-{datetime.now(timezone.utc).date().isoformat()}.json"),
    )
    args = parser.parse_args()

    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        print("TOGETHER_API_KEY is not set in this shell. Export it yourself and re-run.", file=sys.stderr)
        return 2

    rows = load_seed_rows(STEP1) if args.seed_only else load_eval_rows(STEP1)
    if args.limit:
        rows = rows[: args.limit]

    report = {
        "ai_provider_changed": False,
        "cards_approved": False,
        "model": args.model,
        "eval_set": "seed_only" if args.seed_only else "seed_plus_corpus",
        "row_count": len(rows),
    }
    print(json.dumps(report, indent=2))

    records = []
    for i, row in enumerate(rows, start=1):
        try:
            raw = call_together(args.model, prompt_messages(row), api_key, args.max_tokens)
            scored = score_row(row, raw)
        except Exception as exc:
            scored = {"id": row["id"], "task": row["task"], "pass": False, "violations": [f"call_error: {exc}"]}
        records.append(scored)
        status = "pass" if scored["pass"] else "FAIL"
        print(f"[{i}/{len(rows)}] {scored['id']}: {status} {scored['violations']}")

    passed = sum(1 for item in records if item["pass"])
    report.update(
        {
            "passed": passed,
            "failed": len(records) - passed,
            "pass_rate": passed / len(records) if records else 0.0,
            "breakdown": breakdown_by_move_and_objection(rows, records),
            "records": records,
        }
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k not in ("records",)}, indent=2))
    print(f"wrote {out}")
    return 0 if passed == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
