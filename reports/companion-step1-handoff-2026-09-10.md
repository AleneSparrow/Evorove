# Companion Step 1 handoff — 10 September 2026

Cycle 2 mouth only. Production mouth stays the configured LLM. `SalesPolicyEngine` still chooses `SalesMove`. This closes Step 1 (legal corpus + dataset + eval). It does **not** start Step 2.

## Changed files (this close)

- `reports/companion-step1-handoff-2026-09-10.md` (this file)
- `docs/foundation-alignment-stage-ru.md` (step 12 status sentence only)

No ingest this pass. No new rulebook pairs. No card approval. No training job.

## Corpus / dataset / eval state (10 September)

Registry `docs/sales-knowledge/corpus-registry.json` (`updated_at` 2026-09-10T04:39:05+00:00):

| Count | Value |
| --- | --- |
| `deposited_files` | 48 in `private/sales-corpus/incoming/` (gitignored) |
| `sft_core_titles` | 17 (`CORE_CATALOG_IDS`) |
| `archive_mapped` | 19 |
| `unmapped` | 11 |
| derived analyzer | 105 (core-only paraphrases, no chapter text) |
| derived generator | 105 (core-only paraphrases, no chapter text) |
| seed analyzer | 10 |
| seed generator | 9 positive + 7 negative |
| fixture version | `2026-09-10.v1` |
| `training_job_started` | false |
| `cards_approved` | false |
| `ready_for_step2_training` | true = at least one **core** copy is deposited, **not** “start a job” |
| `owner_zip_is_positive_sft` | false |
| Incoming | still open; catalog not frozen |

Core titles (SFT lane): agile-selling, brody-email, challenger-sale, fanatical-prospecting, getting-to-yes, hbr-sales, hsieh-service, influence, never-split-the-difference, rysev-active-sales, sandler-rules, selling-to-big-companies, spin-selling, storybrand, storybrand-2, storybrand-funnel, zaid-sales-bible.

Archive stays registered, no SFT rows. Fixtures overlay: FFF, scarcity, discount, guarantee, outbound thanks, two questions, invented gift, injection, STOP.

## Commands

```bash
python3 -m pytest tests/test_companion_step1_dataset.py tests/test_companion_corpus_ingest.py -q
```

Pass: 16 passed. Ingest not run (tests green). No GPU/hosted job. No `AI_PROVIDER` change.

Live leftover evals (`scripts/sales_turn_analysis_eval.py`, `scripts/sales_response_generation_eval.py`): **not run (no secrets read)**. Process env had no Anthropic/OpenAI keys; `.env` not opened. Production eval fixtures not relaxed. No new `reports/sales-*-eval-*.json`.

## Licence breakdown

- **Core (SFT):** 17 mapped titles with owner-deposited copies (`licence: my-copy`). Derived JSONL only from this lane.
- **Archive (mapped-not-core):** 19 titles registered, extracted locally, **no** derived SFT rows (retail, career/psych, skip polarity, office-politics counterexample).
- **Unmapped:** 11 filenames registered, title-only provenance; owner should name methodology before any SFT.
- **Owner zip skip:** `evals/companion_step1/data/alpaca_*.jsonl`, `chatml_*.jsonl`, `sharegpt_*.jsonl` are **not** positive SFT (Feel-Felt-Found taught as correct). Zip itself is in ingest `SKIP_FILENAMES`.
- `needs_licence_until_deposited`: empty. SPIN / Challenger / Influence / Voss / Fanatical Prospecting are deposited, not title-only queues.

## Cards

Still **unapproved**, version 0. Overlay `evals/companion_step1/derived/candidate-cards-from-deposits.json` stays candidate. No Settings import. FFF still a negative. Card 007 still out of corpus.

## Remaining holes (not filled this pass)

- `SCHEDULE_CALLBACK` almost absent (no seed/derived generator rows).
- `REFLECT_CUSTOMER_NEED` and `NURTURE_WITHOUT_PRESSURE` still thin (few derived paraphrases).
- `END_CONTACT` is one STOP row in seed (plus one derived).
- Companion generator is not wired to production (`src/ai/sales_response_models.py` experiment lane).

## Ready for Step 2 training

**No.**

`ready_for_step2_training: true` in the registry only means a core copy exists. FOUNDATION / the alignment stage have **not** opened a Step 2 slice. Training job still no.
