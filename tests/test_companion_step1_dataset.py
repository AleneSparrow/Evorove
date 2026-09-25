"""Companion Step 1 dataset: schemas only, no training job, no card approval."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.ai.sales_models import SalesTurnAnalysisOutput
from src.ai.sales_response_models import SalesResponseOutput, check_move_matches_approved
from src.domain.sales import SalesMove

ROOT = Path(__file__).resolve().parents[1] / "evals" / "companion_step1"
ANALYZER = ROOT / "data" / "analyzer.jsonl"
GENERATOR = ROOT / "data" / "generator.jsonl"
MANIFEST = Path(__file__).resolve().parents[1] / "docs" / "sales-knowledge" / "corpus-manifest-step1.md"


def _rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_analyzer_targets_match_schema_and_verbatim_evidence() -> None:
    rows = _rows(ANALYZER)
    assert len(rows) == 18  # 14 original + 4 added in the 12 Sep 2026 objection-type coverage pass
    for row in rows:
        target = SalesTurnAnalysisOutput.model_validate(row["target"])
        message = row["customer_message"]
        for signal in target.signals:
            assert signal.evidence in message
        for objection in target.objections:
            assert objection.evidence in message
        if target.requires_human:
            assert target.recommended_moves == [SalesMove.HANDOFF_TO_HUMAN]


def test_generator_targets_echo_approved_move() -> None:
    rows = _rows(GENERATOR)
    positives = [row for row in rows if row["polarity"] == "positive"]
    negatives = [row for row in rows if row["polarity"] == "negative"]
    assert len(positives) == 10
    assert len(negatives) == 7
    for row in rows:
        output = SalesResponseOutput.model_validate(row["target"])
        approved = SalesMove(row["approved_move"])
        assert check_move_matches_approved(output, approved) == []
        lowered = output.message_text.casefold()
        if row["id"] == "gen-greet-outbound-001":
            assert "thanks for reaching out" not in lowered
            assert "you reached out" not in lowered
        if row["polarity"] == "negative":
            bad = row["bad_message_text"].casefold()
            assert bad != lowered
            if "fff" in row["id"]:
                assert "i understand how you feel" in bad
            for pattern in row.get("forbidden_patterns") or []:
                assert re.search(pattern, output.message_text, flags=re.IGNORECASE) is None, row["id"]


def test_owner_alpaca_pack_is_not_the_companion_sft_set() -> None:
    alpaca = (ROOT / "data" / "alpaca_val.jsonl").read_text(encoding="utf-8")
    assert "Feel-Felt-Found" in alpaca
    companion_gen = GENERATOR.read_text(encoding="utf-8")
    assert "I understand how you feel. Others have felt" in companion_gen
    assert '"polarity": "negative"' in companion_gen


def test_manifest_does_not_start_a_training_job() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    assert "Ready for Step 2 training?" in text
    assert "LibGen" in text
    assert "does **not** start a training job" in text or "never starts a training job" in text


def test_fixtures_cover_required_negative_themes() -> None:
    fixtures = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
    blob = ANALYZER.read_text(encoding="utf-8") + "\n" + GENERATOR.read_text(encoding="utf-8")
    lowered = blob.casefold()
    checks = {
        "feel_felt_found": "i understand how you feel",
        "fake_scarcity": "spots are filling",
        "invented_discount": "20% off",
        "invented_guarantee": "guarantee you'll",
        "outbound_thanks_for_reaching_out": "thanks for reaching out",
        "two_questions": "gen-neg-two-questions-001",
        "invented_gift": "gen-neg-invented-gift-001",
        "prompt_injection": "ignore previous instructions",
        "STOP": "stop. do not text me again.",
    }
    for theme in fixtures["required_negative_themes"]:
        needle = checks[theme]
        assert needle.casefold() in lowered, theme
    assert fixtures["counts"]["generator_negative"] == 7
    assert fixtures["sft_lane"] == "core_only"


def test_derived_jsonl_is_core_lane_only() -> None:
    from src.companion_corpus.known_titles import CORE_CATALOG_IDS

    catalogs: set[str] = set()
    for path, task in (
        (ROOT / "data" / "derived" / "analyzer_from_corpus.jsonl", "analyzer"),
        (ROOT / "data" / "derived" / "generator_from_corpus.jsonl", "generator"),
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            catalogs.add(row["catalog_id"])
            if task == "analyzer":
                target = SalesTurnAnalysisOutput.model_validate(row["target"])
                for signal in target.signals:
                    assert signal.evidence in row["customer_message"]
            else:
                output = SalesResponseOutput.model_validate(row["target"])
                assert check_move_matches_approved(output, SalesMove(row["approved_move"])) == []
    assert catalogs <= CORE_CATALOG_IDS


LIVE_PATH_MOVES = {
    "GREET_AND_SET_CONTEXT",
    "ASK_DISCOVERY_QUESTION",
    "REFLECT_CUSTOMER_NEED",
    "CONFIRM_CUSTOMER_NEED",
    "PRESENT_RELEVANT_VALUE",
    "DIAGNOSE_OBJECTION",
    "ANSWER_OBJECTION",
    "CHECK_OBJECTION_RESOLUTION",
    "ASK_FOR_COMMITMENT",
    "OFFER_BOOKING_SLOTS",
    "SEND_CONTEXTUAL_FOLLOW_UP",
    "NURTURE_WITHOUT_PRESSURE",
    "END_CONTACT",
}


def test_seed_and_derived_cover_live_path_moves() -> None:
    moves: set[str] = set()
    for path in (
        GENERATOR,
        ROOT / "data" / "derived" / "generator_from_corpus.jsonl",
    ):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            moves.add(row["approved_move"])
    missing = LIVE_PATH_MOVES - moves
    assert not missing, missing


