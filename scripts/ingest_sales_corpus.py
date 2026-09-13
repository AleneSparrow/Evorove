#!/usr/bin/env python3
"""Register owner-deposited sales books. Does not train, download, or approve cards.

Usage (from repo root):

    python scripts/ingest_sales_corpus.py
    python scripts/ingest_sales_corpus.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.companion_corpus.ingest import corpus_status, ingest_sales_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print corpus-registry.json without scanning files",
    )
    args = parser.parse_args()
    if args.status:
        payload = corpus_status()
    else:
        payload = ingest_sales_corpus()
    print(json.dumps(
        {
            "ready_for_step2_training": payload.get("ready_for_step2_training"),
            "training_job_started": payload.get("training_job_started", False),
            "cards_approved": payload.get("cards_approved", False),
            "deposited_files": payload.get("deposited_files", 0),
            "mapped_known_titles": payload.get("mapped_known_titles", []),
            "sft_core_titles": payload.get("sft_core_titles", []),
            "archive_mapped_titles": payload.get("archive_mapped_titles", []),
            "unmapped_files": payload.get("unmapped_files", []),
            "errors": payload.get("errors", []),
            "next_owner_step": payload.get("next_owner_step"),
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
