"""Export companion core JSONL to ChatML for local LoRA. Does not train."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.companion_corpus.sft_export import collect_sft_records, write_sft


def main() -> int:
    summary = write_sft(collect_sft_records())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
