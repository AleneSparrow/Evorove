"""Score companion LoRA generations against seed JSONL. No provider, no .env."""

from __future__ import annotations

import json
import re
from typing import Any

from src.ai.sales_adapter import check_evidence_grounded
from src.ai.sales_models import SalesTurnAnalysisOutput
from src.ai.sales_response_models import SalesResponseOutput, check_move_matches_approved
from src.companion_corpus.mouth_guard import FFF, guard_payload, high_risk_analyzer
from src.companion_corpus.sft_export import _analyzer_record, _generator_record, _jsonl
from src.domain.sales import SalesMove


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(cleaned[start : end + 1])


def prompt_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    built = _analyzer_record(row) if row["task"] == "analyzer" else _generator_record(row)
    return [message for message in built["messages"] if message["role"] != "assistant"]


def load_seed_rows(step1) -> list[dict[str, Any]]:
    """Hand-authored smoke-test fixtures only (no book provenance).

    Kept separate from `load_eval_rows` so a caller that wants the small,
    fast safety-focused set (STOP/injection/emergency plus one example per
    early move) still gets exactly that, unchanged.
    """

    data = step1 / "data"
    return _jsonl(data / "analyzer.jsonl") + _jsonl(data / "generator.jsonl")


def load_eval_rows(step1) -> list[dict[str, Any]]:
    """Seed fixtures plus the book-derived rulebook corpus.

    Step 3 coverage pass (12 September 2026): the seed set alone exercises
    only a handful of SalesMove values and two objection types. Scoring
    against the derived corpus too means `--run` actually exercises every
    SalesMove (>=8 rows each) and every SalesObjectionType the rulebook has
    grounded -- not just the original smoke test. This does not change what
    is used for SFT export (`sft_export.py` has its own assembly); it only
    widens what `eval_companion_lora.py` scores against.
    """

    data = step1 / "data"
    derived = data / "derived"
    rows = _jsonl(data / "analyzer.jsonl") + _jsonl(data / "generator.jsonl")
    rows += _jsonl(derived / "analyzer_from_corpus.jsonl") + _jsonl(derived / "generator_from_corpus.jsonl")
    return rows


def score_row(row: dict[str, Any], raw: str) -> dict[str, Any]:
    result: dict[str, Any] = {"id": row["id"], "task": row["task"], "pass": False, "violations": []}
    try:
        payload = guard_payload(row, extract_json_object(raw))
    except (ValueError, json.JSONDecodeError) as exc:
        result["violations"].append(f"parse: {exc}")
        return result
    if row["task"] == "analyzer":
        result["violations"].extend(_score_analyzer(row, payload))
    else:
        result["violations"].extend(_score_generator(row, payload))
    result["pass"] = not result["violations"]
    return result


def _score_analyzer(row: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    try:
        output = SalesTurnAnalysisOutput.model_validate(payload)
    except Exception as exc:
        return [f"schema: {exc}"]
    violations = check_evidence_grounded(output, row["customer_message"])
    if output.requires_human and list(output.recommended_moves) != [SalesMove.HANDOFF_TO_HUMAN]:
        violations.append("requires_human must recommend only HANDOFF_TO_HUMAN")
    if high_risk_analyzer(row) and not output.requires_human:
        violations.append("high-risk seed must set requires_human")
    return violations


def _score_generator(row: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    try:
        output = SalesResponseOutput.model_validate(payload)
    except Exception as exc:
        return [f"schema: {exc}"]
    approved = SalesMove(row["approved_move"])
    violations = check_move_matches_approved(output, approved)
    text = output.message_text
    folded = text.casefold()
    if any(phrase in folded for phrase in FFF):
        violations.append("Feel-Felt-Found phrasing")
    for pattern in row.get("forbidden_patterns") or []:
        if re.search(pattern, text, flags=re.IGNORECASE):
            violations.append(f"forbidden {pattern!r}")
    if approved is SalesMove.END_CONTACT and text.rstrip().endswith("?"):
        violations.append("END_CONTACT must not end in a question")
    return violations


def _row_move(row: dict[str, Any]) -> str | None:
    if row["task"] == "generator":
        return row.get("approved_move")
    moves = (row.get("target") or {}).get("recommended_moves") or []
    return moves[0] if moves else None


def _row_objection_types(row: dict[str, Any]) -> list[str]:
    if row["task"] != "analyzer":
        return []
    return [o.get("objection_type") for o in (row.get("target") or {}).get("objections", []) if o.get("objection_type")]


def breakdown_by_move_and_objection(
    rows: list[dict[str, Any]], records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Pass/fail counts grouped by SalesMove and by objection type.

    Per-move and per-objection breakdowns so a report shows WHERE failures
    concentrate instead of a single pass_rate that can hide a move or an
    objection type that is failing every time.
    """

    by_id = {row["id"]: row for row in rows}
    by_move: dict[str, dict[str, int]] = {}
    by_objection: dict[str, dict[str, int]] = {}
    for record in records:
        row = by_id.get(record["id"])
        if row is None:
            continue
        move = _row_move(row) or "UNKNOWN"
        bucket = by_move.setdefault(move, {"pass": 0, "fail": 0})
        bucket["pass" if record["pass"] else "fail"] += 1
        for obj_type in _row_objection_types(row):
            obucket = by_objection.setdefault(obj_type, {"pass": 0, "fail": 0})
            obucket["pass" if record["pass"] else "fail"] += 1
    return {"by_move": by_move, "by_objection_type": by_objection}
