# Companion Step 1 handoff — 8 September 2026

## Changed files

- `docs/sales-knowledge/corpus-manifest-step1.md`
- `docs/sales-knowledge/companion-dataset-spec.md`
- `docs/sales-knowledge/candidate-knowledge-cards-step1-open-sources-2026-09-08.md`
- `evals/companion_step1/data/analyzer.jsonl` (10)
- `evals/companion_step1/data/generator.jsonl` (9 positive, 5 negative)
- `evals/companion_step1/fixtures.json`
- `evals/companion_step1/README.md` (banner: not SFT-ready)
- `tests/test_companion_step1_dataset.py`
- `docs/sales-agent-implementation-plan-ru.md` (0.3 / 21 status)
- `docs/foundation-alignment-stage-ru.md` (step 12)

## Commands

```bash
python3 -m pytest tests/test_companion_step1_dataset.py -q
```

Pass: 4 passed. No GPU job. No `AI_PROVIDER` change. Live Anthropic eval not run (no secrets read).

## Sources skipped for licence

SPIN, Challenger, Influence, Voss, Fanatical Prospecting: title-only, **needs-licence**.  
Owner zip Q&A: deposited but **skip as positive SFT** (Feel-Felt-Found taught as correct; not `SalesTurnAnalysis` / `SalesResponseOutput`).  
`sources.csv` (84 URLs): needs-licence queue, text not copied.

Open/government used as title-only hubs: FTC advertising guidance, FCC STOP guide, FCC 24-24, Hopkins 1923 PD (no scan committed).

## Cards

Still **unapproved**. New candidates 009–011 only. 007 still out of corpus. FFF still a negative. No Settings import.

## Ready for Step 2 training

**No.**
