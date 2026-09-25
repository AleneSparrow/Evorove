"""Offline companion LoRA eval on seed JSONL. Default is dry-run.

Does not read .env. Does not change AI_PROVIDER. Does not approve cards.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.companion_corpus.lora_eval import (
    breakdown_by_move_and_objection,
    load_eval_rows,
    prompt_messages,
    score_row,
)
from src.companion_corpus.sft_export import STEP1

DEFAULT_MODEL = ROOT / "private" / "companion-lora" / "base-qwen2.5-7b"
DEFAULT_ADAPTER = ROOT / "private" / "companion-lora" / "adapter-qwen2.5-7b-v3"


def _generate(model, tokenizer, messages: list[dict[str, str]], max_tokens: int) -> str:
    from mlx_lm import generate

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Generate with mlx. Loads the 7B weights and can freeze this Mac. Default is dry-run.",
    )
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--adapter-path", default=str(DEFAULT_ADAPTER))
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports" / f"companion-lora-eval-{datetime.now(timezone.utc).date().isoformat()}.json"),
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help=(
            "Score only the small hand-authored smoke-test fixtures (original behavior), "
            "not the full book-derived corpus. Useful for a fast sanity check."
        ),
    )
    args = parser.parse_args()
    from src.companion_corpus.lora_eval import load_seed_rows

    rows = load_seed_rows(STEP1) if args.seed_only else load_eval_rows(STEP1)
    report = {
        "ai_provider_changed": False,
        "cards_approved": False,
        "seed_rows": len(rows),
        "eval_set": "seed_only" if args.seed_only else "seed_plus_corpus",
        "model": args.model,
        "adapter_path": args.adapter_path,
        "mode": "live" if args.run else "dry_run",
    }
    if not args.run:
        print(json.dumps(report, indent=2))
        print("Dry-run only. Pass --run to generate with the local adapter.")
        return 0
    from mlx_lm import load

    model, tokenizer = load(args.model, adapter_path=args.adapter_path)
    records = []
    for row in rows:
        raw = _generate(model, tokenizer, prompt_messages(row), args.max_tokens)
        scored = score_row(row, raw)
        scored["raw"] = raw
        records.append(scored)
        print(f"{scored['id']}: {'pass' if scored['pass'] else 'FAIL'} {scored['violations']}")
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
    print(json.dumps({k: report[k] for k in report if k != "records"}, indent=2))
    print(f"wrote {out}")
    return 0 if passed == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
