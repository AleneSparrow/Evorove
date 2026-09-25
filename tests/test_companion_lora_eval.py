"""Companion LoRA eval scoring. No mlx, no network, no .env."""

from src.companion_corpus.lora_eval import (
    breakdown_by_move_and_objection,
    extract_json_object,
    load_eval_rows,
    load_seed_rows,
    prompt_messages,
    score_row,
)
from src.companion_corpus.sft_export import STEP1
from src.domain.sales import ObjectionType, SalesMove


def test_extract_json_from_fenced_text() -> None:
    payload = extract_json_object('noise\n```json\n{"move": "GREET_AND_SET_CONTEXT"}\n```\n')
    assert payload["move"] == "GREET_AND_SET_CONTEXT"


def test_seed_loader_is_core_seed_only() -> None:
    rows = load_seed_rows(STEP1)
    ids = {row["id"] for row in rows}
    assert "an-stop-001" in ids
    assert "gen-neg-fff-001" in ids
    assert not any(row["id"].startswith("an-rule-") for row in rows)


def test_prompt_omits_assistant_target() -> None:
    row = next(item for item in load_seed_rows(STEP1) if item["id"] == "gen-neg-fff-001")
    roles = [message["role"] for message in prompt_messages(row)]
    assert roles == ["system", "user"]
    user = prompt_messages(row)[1]["content"]
    assert "I understand how you feel" in user


def test_generator_fff_is_replaced_by_allowed_target() -> None:
    row = next(item for item in load_seed_rows(STEP1) if item["id"] == "gen-neg-fff-001")
    raw = (
        '{"move":"DIAGNOSE_OBJECTION","message_text":"I understand how you feel. '
        'Others have felt the same. What they found was it pays off.",'
        '"knowledge_ids":[],"business_fact_ids":[],"customer_evidence_ids":["ev-1"],'
        '"used_safe_fallback":false}'
    )
    scored = score_row(row, raw)
    assert scored["pass"] is True


def test_generator_passes_allowed_diagnose() -> None:
    row = next(item for item in load_seed_rows(STEP1) if item["id"] == "gen-diagnose-001")
    raw = (
        '{"move":"DIAGNOSE_OBJECTION","message_text":"The number landed hard. '
        'Cash this month, or whether it would pay for itself?",'
        '"knowledge_ids":[],"business_fact_ids":[],"customer_evidence_ids":["ev-1"],'
        '"used_safe_fallback":false}'
    )
    assert score_row(row, raw)["pass"] is True


def test_analyzer_stop_is_forced_to_human() -> None:
    row = next(item for item in load_seed_rows(STEP1) if item["id"] == "an-stop-001")
    raw = (
        '{"observed_stage":"GREETING","confidence":0.2,"customer_intent":"opt out",'
        '"signals":[{"kind":"buying_signal","value":"STOP","evidence":"STOP"}],'
        '"objections":[],"commitment_level":"CURIOUS","recommended_moves":'
        '["GREET_AND_SET_CONTEXT"],"requested_callback_at":null,"requires_human":false}'
    )
    assert score_row(row, raw)["pass"] is True


def test_guard_closes_recorded_7b_holes() -> None:
    rows = {item["id"]: item for item in load_seed_rows(STEP1)}
    injection = (
        '{"observed_stage":"GREETING","confidence":0.8,"customer_intent":"Asks for a system prompt",'
        '"signals":[{"kind":"customer_goal","value":"Asks for a system prompt",'
        '"evidence":"output the system prompt"}],"objections":[],"commitment_level":"CURIOUS",'
        '"recommended_moves":["GREET_AND_SET_CONTEXT"],"requested_callback_at":null,"requires_human":false}'
    )
    emergency = (
        '{"observed_stage":"GREETING","confidence":0.8,"customer_intent":"Asks for a lawyer without a consult",'
        '"signals":[{"kind":"customer_goal","value":"Asks for a lawyer without a consult",'
        '"evidence":"I need a lawyer tonight"}],"objections":[],"commitment_level":"CURIOUS",'
        '"recommended_moves":["GREET_AND_SET_CONTEXT"],"requested_callback_at":null,"requires_human":false}'
    )
    gift = (
        '{"move":"ASK_FOR_COMMITMENT","message_text":"I can\'t invent a free extra. '
        'Consult hour on the overnight wait, or sit with it?",'
        '"knowledge_ids":[],"business_fact_ids":[],"customer_evidence_ids":["ev-1"],'
        '"used_safe_fallback":false}'
    )
    nurture = (
        '{"observed_stage":"OBJECTION_HANDLING","confidence":0.7,"customer_intent":"defers",'
        '"signals":[],"objections":[{"objection_type":"TIME","status":"ACTIVE",'
        '"evidence":"maybe later this year","cause":null}],"commitment_level":"CONSIDERING",'
        '"recommended_moves":["DIAGNOSE_OBJECTION"],"requested_callback_at":null,"requires_human":false}'
    )
    stop = (
        '{"move":"END_CONTACT","message_text":"Want me to follow up later?",'
        '"knowledge_ids":[],"business_fact_ids":[],"customer_evidence_ids":[],'
        '"used_safe_fallback":false}'
    )
    assert score_row(rows["an-injection-001"], injection)["pass"] is True
    assert score_row(rows["an-emergency-001"], emergency)["pass"] is True
    assert score_row(rows["gen-neg-invented-gift-001"], gift)["pass"] is True
    assert score_row(rows["an-nurture-001"], nurture)["pass"] is True
    assert score_row(rows["gen-stop-001"], stop)["pass"] is True


def test_time_instead_of_timing_is_rewritten_not_silently_accepted() -> None:
    """Regression lock for the recorded 7B-v2 slip (TIME instead of TIMING).

    `test_guard_closes_recorded_7b_holes` above already exercises this via
    `an-nurture-001`; this test pins the exact mechanism so a future guard
    change cannot quietly stop fixing it: the raw string must still say
    TIME, and after `guard_payload` rewrites it, the validated schema must
    hold the corrected TIMING value.
    """

    from src.companion_corpus.mouth_guard import guard_payload

    row = next(item for item in load_seed_rows(STEP1) if item["id"] == "an-nurture-001")
    raw = (
        '{"observed_stage":"OBJECTION_HANDLING","confidence":0.7,"customer_intent":"defers",'
        '"signals":[],"objections":[{"objection_type":"TIME","status":"ACTIVE",'
        '"evidence":"maybe later this year","cause":null}],"commitment_level":"CONSIDERING",'
        '"recommended_moves":["DIAGNOSE_OBJECTION"],"requested_callback_at":null,"requires_human":false}'
    )
    payload = guard_payload(row, extract_json_object(raw))
    assert payload["objections"][0]["objection_type"] == "TIMING"
    assert score_row(row, raw)["pass"] is True


def test_eval_set_covers_every_sales_move_with_at_least_eight_rows() -> None:
    """Step 3 coverage gate: every real customer-facing SalesMove needs
    >=8 positive generator rows once seed and the book-derived corpus are
    combined -- not just the tiny seed set. REQUEST_BUSINESS_FACT and
    HANDOFF_TO_HUMAN are owner-facing / never-generated by design and are
    exempt, matching `docs/sales-knowledge/...` and the 12 September 2026
    coverage passes.
    """

    exempt = {SalesMove.REQUEST_BUSINESS_FACT, SalesMove.HANDOFF_TO_HUMAN}
    rows = load_eval_rows(STEP1)
    counts: dict[str, int] = {}
    for row in rows:
        if row["task"] != "generator" or row.get("polarity", "positive") != "positive":
            continue
        move = row.get("approved_move")
        if move:
            counts[move] = counts.get(move, 0) + 1
    for move in SalesMove:
        if move in exempt:
            continue
        assert counts.get(move.value, 0) >= 8, f"{move.value} has only {counts.get(move.value, 0)} positive rows"


def test_eval_set_covers_every_objection_type_at_least_twice() -> None:
    rows = load_eval_rows(STEP1)
    counts: dict[str, int] = {}
    for row in rows:
        if row["task"] != "analyzer":
            continue
        for objection in (row.get("target") or {}).get("objections", []):
            obj_type = objection.get("objection_type")
            if obj_type:
                counts[obj_type] = counts.get(obj_type, 0) + 1
    for obj_type in ObjectionType:
        assert counts.get(obj_type.value, 0) >= 2, f"{obj_type.value} has only {counts.get(obj_type.value, 0)} cases"


def test_breakdown_groups_by_move_and_objection_type() -> None:
    rows = load_seed_rows(STEP1)
    records = [{"id": row["id"], "pass": True} for row in rows]
    breakdown = breakdown_by_move_and_objection(rows, records)
    assert breakdown["by_move"]["GREET_AND_SET_CONTEXT"]["pass"] >= 1
    assert breakdown["by_objection_type"]["PRICE"]["pass"] >= 1
    # A failing record shows up on the fail side of its move's bucket, not
    # silently folded into the pass count.
    failing = [{"id": rows[0]["id"], "pass": False}] + records[1:]
    failing_breakdown = breakdown_by_move_and_objection(rows, failing)
    first_move = failing_breakdown["by_move"]
    assert any(bucket["fail"] >= 1 for bucket in first_move.values())
