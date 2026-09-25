# Hosted GPU mouth — Together (not Railway, not this Mac)

Cycle 2 mouth only. `SalesPolicyEngine` still chooses `SalesMove`. Mac mlx
adapters are Apple Metal; they are **not** uploaded. Together retrains LoRA
from the same ChatML. Production `AI_PROVIDER` stays unchanged until the
owner accepts evals and says so.

**Rebuilt 12 September 2026** after the step 3 coverage pass: every real
customer-facing `SalesMove` now has >=8 grounded positive rows (was as low
as 0 for two moves that morning), every `ObjectionType` has >=2, and the
anti-verbatim-quote guard (`src/companion_corpus/mouth_guard.py`) is wired
in front of generation — see `reports/companion-step3-coverage-pass1-2026-09-12.md`
for the full walk-through.

## Files

| File | Role |
| --- | --- |
| `together_train.jsonl` | OpenAI chat `messages` only — **358 rows** (was 263) |
| `together_valid.jsonl` | Held-out slice — **42 rows** (was 29) |
| `manifest.json` | Counts; `training_job_started` is false |

Rebuild:

```bash
python3 scripts/export_companion_hosted.py
```

Never upload `evals/companion_step1/data/alpaca_*.jsonl`, `chatml_*.jsonl`, or
`sharegpt_*.jsonl`.

## Owner steps (agent does not create accounts or paste keys)

1. Sign up at [together.ai](https://together.ai) and create an API key yourself.
2. Upload `together_train.jsonl` (and valid) from this folder or from Drive
   `gdrive:evorove-companion/hosted-sft/`.
3. Start a **LoRA** job on a listed Qwen instruct ~7B (dashboard model list).
4. Deploy their OpenAI-compatible endpoint.
5. Later, in Railway Variables (not via the agent): `OPENAI_BASE_URL`,
   `OPENAI_API_KEY`, `OPENAI_MODEL` — only after you accept evals and say to
   switch. Keep `mouth_guard` in front of every generation — this is not
   optional: `mouth_guard.check_verbatim_quote` is what stops the model
   from ever quoting a depositied book to a customer, and the STOP/
   injection/emergency escalation lives there too.

Copy to Drive (not NFS `cp`):

```bash
rclone copy evals/companion_step2/hosted gdrive:evorove-companion/hosted-sft/
```
