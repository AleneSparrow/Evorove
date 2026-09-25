"""Export Together-shaped ChatML. Does not train, upload, or change AI_PROVIDER.

Does not read .env. A hosted GPU job starts only after the owner creates a
Together account and runs their CLI with their own key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.companion_corpus.sft_export import collect_sft_records, write_sft

DRIVE = "gdrive:evorove-companion/hosted-sft/"


def main() -> int:
    summary = write_sft(collect_sft_records())
    hosted = summary["hosted"]
    report = {
        "training_job_started": False,
        "ai_provider_changed": False,
        "cards_approved": False,
        "hosted": hosted,
        "owner_creates_together_account": True,
        "drive": DRIVE,
        "next": [
            "Owner signs up at together.ai (agent does not create accounts).",
            "Upload evals/companion_step2/hosted/together_train.jsonl (and valid).",
            "LoRA on a Qwen instruct 7B if listed; never alpaca/chatml/sharegpt.",
            "Do not set Railway AI_PROVIDER until evals pass and the owner says so.",
            f"Copy with: rclone copy {hosted['dest']} {DRIVE}",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
