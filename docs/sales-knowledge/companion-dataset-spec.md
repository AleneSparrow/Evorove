# Companion dataset spec — Step 1 (no weights)

Companion reads language and phrases a **server-approved** `SalesMove`. It does not search people, set price, grant a discount, book a slot, or choose a different move.

Records live under `evals/companion_step1/`. Never under `private/sales-corpus/`. No book chapters.

## Tasks

### Analyzer

Map `customer_message` + `profile_context` → `src.ai.sales_models.SalesTurnAnalysisOutput`.

- `evidence` on signals and objections must be a verbatim substring of `customer_message`.
- `recommended_moves` are advisory. The engine still decides.
- If `requires_human` is true, `recommended_moves` must be exactly `["HANDOFF_TO_HUMAN"]`.
- Unresolved objections require `observed_stage` `OBJECTION_HANDLING`.
- Do not recommend `ANSWER_OBJECTION` while `cause` is null.

File: `evals/companion_step1/data/analyzer.jsonl` (seed). Extra rows after a deposited book: `evals/companion_step1/data/derived/analyzer_from_corpus.jsonl`.

### Generator

Map `approved_move` + allowed facts/evidence → `src.ai.sales_response_models.SalesResponseOutput`.

- `move` must equal `approved_move`.
- No invented price, discount, guarantee, or scarcity.
- Outbound `GREET_AND_SET_CONTEXT` must not assume the person wrote in (“thanks for reaching out”, “you reached out”). First outbound hello is Evorove for {business}, not the tenant’s own account.
- `END_CONTACT` after STOP is a close, not a nurture question.

File: `evals/companion_step1/data/generator.jsonl` (seed). Extra rows: `evals/companion_step1/data/derived/generator_from_corpus.jsonl`.

## Polarity

| `polarity` | Meaning |
| --- | --- |
| `positive` | Imitate `target` |
| `negative` | Do **not** imitate `bad_message_text` / Feel-Felt-Found / fake scarcity. `target` is the allowed wording |

## Eval fixtures

`evals/companion_step1/fixtures.json` is the scored set (positives and negatives). It does not replace `evals/sales_turn_analysis/` or `evals/sales_response_generation/`; it adds companion-specific cases (outbound greet, FFF refusal, dump-style discount demand).

Existing production evals stay the source of truth for prompt hashes. This folder must not weaken them.

Seed plus core derived JSONL should cover the live path: greet, one discovery question, reflect/confirm, relevant value, diagnose, answer from a listed fact, check resolution, small commitment, listed booking slots, follow-up, nurture, STOP/end.

## What is not this dataset

`evals/companion_step1/data/alpaca_*.jsonl`, `chatml_*.jsonl`, `sharegpt_*.jsonl` are the owner’s textbook pack. They are **not** mapped to `SalesTurnAnalysisOutput` / `SalesResponseOutput`. Feel-Felt-Found is taught there as a correct answer. Do not feed them to Step 2 as positive sales-agent SFT.

Owner book drop: `private/sales-corpus/incoming/` then `python scripts/ingest_sales_corpus.py`. The folder stays open — more purchased files can be added later. Only **core** conversation-sales titles unlock derived JSONL; other deposits are archive. See `docs/sales-knowledge/how-to-deposit-books-ru.md`.

## Step 2 (local LoRA)

Owner opened local LoRA on 10 September 2026. Export: `python3 scripts/export_companion_sft.py`. Jobs that day trained Qwen2.5-3B and Qwen2.5-7B 4bit adapters; they are not production. Another job: `python3 scripts/train_companion_lora.py --run` (Apple Silicon, `mlx-lm`). Dry-run is the default. Do not change production `AI_PROVIDER` in this slice. Guide: `evals/companion_step2/README.md`. Handoff: `reports/companion-step2-handoff-2026-09-10.md`.
