# Prompt: закрыть companion Step 1 (корпус / датасет / eval)

**Дата:** 10 сентября 2026  
**Цикл:** 2 (рот). Не поиск людей, не бронь.  
**Этап:** [`docs/foundation-alignment-stage-ru.md`](../foundation-alignment-stage-ru.md) — шаг 12 закрыт как корпус/eval, **не** training job.  
**Основа:** [`FOUNDATION.md`](../../FOUNDATION.md)

Плотность ядра уже снята (105+105 derived). Следующий агент **не** добавляет пары из книг. Он закрывает Step 1 отчётом и, если runtime уже умеет вызвать Anthropic без чтения `.env`, leftover language evals.

Скопируйте блок ниже агенту из корня `/Users/alenakulish/dev/evorove`.

```text
Read these files first, in this order, and follow them:
1. FOUNDATION.md
2. docs/foundation-alignment-stage-ru.md
3. AGENTS.md
4. CLAUDE.md
5. docs/sales-agent-implementation-plan-ru.md (sections 0, 0.3, 0.4, 21)
6. docs/sales-knowledge/how-to-deposit-books-ru.md
7. docs/sales-knowledge/companion-dataset-spec.md
8. docs/sales-knowledge/corpus-registry.json (status only; no book text)
9. reports/companion-step1-handoff-2026-09-08.md
10. evals/companion_step1/fixtures.json
11. src/companion_corpus/known_titles.py (CORE_CATALOG_IDS)
12. tests/test_companion_step1_dataset.py
13. tests/test_companion_corpus_ingest.py

You are closing companion Step 1 (legal corpus + dataset + eval). You are
not starting Step 2. Production mouth stays the configured LLM.
SalesPolicyEngine still chooses SalesMove.

Current state (do not re-derive from scratch)
- Owner-deposited files: 48 in private/sales-corpus/incoming/ (gitignored).
- Core SFT lane: 17 titles in CORE_CATALOG_IDS. Derived JSONL is core-only.
- Archive (mapped-not-core + 11 unmapped) stays registered, no SFT rows.
- Derived: 105 analyzer + 105 generator paraphrases, no chapter text.
- Seed: analyzer.jsonl 10; generator.jsonl 9 positive + 7 negative.
- Fixtures 2026-09-10.v1: FFF, scarcity, discount, guarantee, outbound
  thanks, two questions, invented gift, injection, STOP.
- Cards: candidate, version 0. Owner zip alpaca/chatml/sharegpt is NOT
  positive SFT (Feel-Felt-Found taught as correct).
- training_job_started: false. ready_for_step2_training: true means at
  least one CORE copy is deposited, not “start a job”.
- Incoming stays open. Do not freeze the catalog.

Assigned work — only this
1. Write reports/companion-step1-handoff-2026-09-10.md in the same shape
   as the 8 September handoff: changed-files list is optional (summarize
   the 10 September corpus/dataset/eval state); commands; pass/fail;
   licence breakdown (core vs archive vs unmapped vs owner-zip skip);
   cards still unapproved; explicit “Ready for Step 2 training: No”
   unless the owner has opened a new slice in FOUNDATION / the stage doc.
   Include counts: deposited_files, sft_core_titles, archive_mapped,
   unmapped, derived row counts, seed counts, fixture version.
   Remaining holes (do not fill them in this pass unless a test is red):
   SCHEDULE_CALLBACK almost absent; REFLECT and NURTURE still thin;
   END_CONTACT is one STOP row; companion generator is not wired to
   production (src/ai/sales_response_models.py experiment lane).
2. Run focused tests:
   python3 -m pytest tests/test_companion_step1_dataset.py tests/test_companion_corpus_ingest.py -q
   Do not weaken tests. Do not start ingest unless a test is red.
3. Leftover language evals (Part 4 of the original Step 1 prompt) ONLY if
   the process already has Anthropic/OpenAI runtime without you reading,
   printing, or editing .env or secrets. If you cannot tell without
   opening .env, skip and write “live eval not run (no secrets read)”.
   Scripts: scripts/sales_turn_analysis_eval.py and
   scripts/sales_response_generation_eval.py. Compare to
   reports/sales-turn-analysis-eval-2026-09-04.json. Do not relax
   production eval fixtures. Save a new report under reports/ if a live
   run actually happens.
4. If the handoff report needs one sentence in
   docs/foundation-alignment-stage-ru.md step 12 / companion line, you
   may note “Step 1 corpus+eval densified 10 Sep 2026; training job still
   no”. Do not mark training as started. Do not open Step 2.

Files you may edit
- reports/companion-step1-handoff-2026-09-10.md (create)
- reports/ only if a live eval actually ran
- docs/foundation-alignment-stage-ru.md only the one status sentence above
- evals/companion_step1/README.md only if the handoff counts are stale there

Do not
- Add more rulebook pairs or “density” rows. Stop mining books.
- Run scripts/ingest_sales_corpus.py unless tests are red.
- Start a GPU/hosted training job, upload weights, or change AI_PROVIDER.
- Approve, publish, or import knowledge cards.
- Feed alpaca/chatml/sharegpt to any trainer.
- Download or scrape books. Copy chapters into git.
- Promote archive titles into CORE_CATALOG_IDS.
- Wire SalesResponseGenerator into production orchestration, API, or
  SalesPolicyEngine.
- Invent SalesStage / SalesMove. Merge SalesStage into ProcessState.
- git push. Read or edit .env / secrets. Create accounts.
- Promise a conversion rate.

Talk to the owner in Russian. Product UI copy stays English.

Handoff back: files changed, commands, pass/fail, whether live eval ran,
Ready for Step 2 training: No, what the owner must decide herself
(open a Step 2 slice vs review candidate cards vs leave production on
the configured LLM).
```

## Что это не делает

Отдельный промпт (не этот), только если владелец явно откроет срез:

- Step 2: hosted LoRA / OpenAI-compatible fine-tune **только** на companion JSONL, рядом с Claude, с откатом;
- утверждение карточек;
- вшивка генератора в прод.
