"""Companion Step 2 SFT export: core JSONL only, no training job."""

from __future__ import annotations

import json
from pathlib import Path

from src.companion_corpus.known_titles import CORE_CATALOG_IDS
from src.companion_corpus.sft_export import collect_sft_records, split_train_valid, write_sft

STEP1_ALPACA = Path(__file__).resolve().parents[1] / "evals" / "companion_step1" / "data" / "alpaca_val.jsonl"


def test_export_skips_owner_zip_and_archive_titles(tmp_path: Path) -> None:
    alpaca = STEP1_ALPACA.read_text(encoding="utf-8")
    assert "Feel-Felt-Found" in alpaca
    records = collect_sft_records()
    dumped = json.dumps(records)
    assert "alpaca_train" not in dumped
    assert "sharegpt" not in dumped
    assert "crossing-the-chasm" not in dumped
    assistants = [
        next(message["content"] for message in row["messages"] if message["role"] == "assistant")
        for row in records
    ]
    assert all("i understand how you feel" not in text.casefold() for text in assistants)
    for row in records:
        if row["id"].startswith(("an-rule-", "gen-rule-")):
            assert any(catalog in row["id"] for catalog in CORE_CATALOG_IDS), row["id"]
    summary = write_sft(records, dest=tmp_path / "sft")
    assert summary["training_job_started"] is False
    assert summary["owner_zip_excluded"] is True
    assert summary["train"] + summary["valid"] == summary["total"]
    assert summary["total"] >= 100
    hosted_dir = tmp_path / "hosted"
    first = json.loads((hosted_dir / "together_train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert set(first) == {"messages"}
    assert {item["role"] for item in first["messages"]} == {"system", "user", "assistant"}
    assert summary["hosted"]["training_job_started"] is False
    assert summary["hosted"]["ai_provider_changed"] is False


def test_high_risk_seed_stays_in_train() -> None:
    records = collect_sft_records()
    train, _valid = split_train_valid(records)
    train_ids = {row["id"] for row in train}
    for prefix in ("an-injection", "an-emergency", "an-stop", "gen-neg-", "gen-stop"):
        assert any(item.startswith(prefix) for item in train_ids), prefix


def test_negative_rows_keep_allowed_target_not_the_bad_line() -> None:
    records = [row for row in collect_sft_records() if row["id"] == "gen-neg-fff-001"]
    assert len(records) >= 1
    user = next(message["content"] for message in records[0]["messages"] if message["role"] == "user")
    assistant = next(message["content"] for message in records[0]["messages"] if message["role"] == "assistant")
    assert "I understand how you feel" in user
    assert "I understand how you feel" not in assistant
    assert json.loads(assistant)["move"] == "DIAGNOSE_OBJECTION"
