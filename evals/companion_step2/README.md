# Companion Step 2 — local LoRA (mouth only)

**Cycle 2 mouth.** `SalesPolicyEngine` still chooses `SalesMove`. This folder is ChatML for a local adapter. It is not production. It does not search people or book a slot.

Owner opened local LoRA on 10 September 2026. **The training job is not started by ingest or by a dry-run.**

## What to train on

| File | Role |
| --- | --- |
| `sft/train.jsonl` | ChatML from core seed + derived analyzer/generator |
| `sft/valid.jsonl` | Held-out slice of the same sources |
| `sft/manifest.json` | Counts; `training_job_started` is always false at export |

Rebuild:

```bash
python3 scripts/export_companion_sft.py
python3 scripts/train_companion_lora.py
```

The second command is a **dry-run** (export + hardware check). It does not download a base model and does not write adapters.

To actually train on Apple Silicon after you install `mlx-lm` yourself:

```bash
python3 -m pip install mlx-lm
python3 scripts/train_companion_lora.py --run
```

Adapters go to `private/companion-lora/` (gitignored). Do not commit weights. Do not change `AI_PROVIDER` until evals pass and you say so.

GPU host (Together): same ChatML, messages-only, in `hosted/`. Mac mlx weights are not uploaded. Owner creates the Together account. Guide: `evals/companion_step2/hosted/README.md`.

## What not to train on

Do **not** pass `evals/companion_step1/data/alpaca_*.jsonl`, `chatml_*.jsonl`, or `sharegpt_*.jsonl` to the trainer. Feel-Felt-Found is a correct answer there. Spec 0.4 forbids that as positive SFT.

Archive-mapped and unmapped books are not in this ChatML.

## After a job

10 September 2026: 3B and 7B 4bit LoRA jobs finished (`lora_exit` 0). Adapters live under `private/companion-lora/` (gitignored) and on Drive `gdrive:evorove-companion/adapters/`. Do not train through the rclone NFS mount; copy with `rclone copy` then train from a local path.

Production `AI_PROVIDER` is unchanged. Local mouth (not production):

```bash
python3 scripts/serve_companion_mouth.py
python3 scripts/serve_companion_mouth.py --run
```

`--run` binds `http://127.0.0.1:8741/v1/chat/completions` (7B + v3 adapter) and runs `mouth_guard` on every completion. Dry-run does not load weights. Cards stay candidate.

Offline seed eval (no `.env`, no `AI_PROVIDER` change). Scoring runs a
deterministic `mouth_guard` so STOP / injection / emergency / gift phrases cannot
ship even if the adapter slips. **Do not `--run` 7B on this Mac while using it —
that freeze is the 7B load, not a hung chat.**

```bash
python3 scripts/eval_companion_lora.py
python3 scripts/eval_companion_lora.py --run
```

Default `--run` uses local 7B base + `adapter-qwen2.5-7b-v3`. Dry-run does not load weights.
