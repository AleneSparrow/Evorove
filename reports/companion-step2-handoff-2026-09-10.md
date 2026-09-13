# Companion Step 2 handoff — 10 September 2026

Cycle 2 mouth only. `SalesPolicyEngine` still chooses `SalesMove`. Production `AI_PROVIDER` unchanged. Cards still candidate.

## Jobs

| Model | Train / val loss @ 200 | Peak mem | Local adapter | Drive |
| --- | --- | --- | --- | --- |
| Qwen2.5-3B-Instruct-4bit | 0.434 / 0.627 | ~2.62 GB | `private/companion-lora/adapter/` | `gdrive:evorove-companion/adapters/qwen2.5-3b/` |
| Qwen2.5-7B-Instruct-4bit (first job) | 0.369 / 0.585 | ~5.31 GB | `private/companion-lora/adapter-qwen2.5-7b/` | `gdrive:evorove-companion/adapters/qwen2.5-7b/` |
| Qwen2.5-7B v3 (val 0.265) | resume +100 | 5.338 GB | `private/companion-lora/adapter-qwen2.5-7b-v3/` | `gdrive:evorove-companion/adapters/qwen2.5-7b-v3/` |
| Qwen2.5-7B v4 | resume +100 | 5.338 GB | `private/companion-lora/adapter-qwen2.5-7b-v4/` | `gdrive:evorove-companion/adapters/qwen2.5-7b-v4/` |

SFT: 292 ChatML rows (`evals/companion_step2/sft/`; 263 train / 29 valid). Owner-zip alpaca/chatml/sharegpt not used.

7B base on Drive: `gdrive:evorove-companion/hf-hub/Qwen2.5-7B-Instruct-4bit/`. Local working copy: `private/companion-lora/base-qwen2.5-7b/` (needed because Hugging Face flock and mlx reads fail on rclone NFS).

Logs: `reports/companion-lora-train-2026-09-10.log`, `reports/companion-lora-train-7b-2026-09-10.log`.

## Seed eval + mouth guard (10 September)

Do **not** run another 7B LoRA job on this Mac: it pins unified memory and freezes the machine.

`src/companion_corpus/mouth_guard.py` patches untrusted adapter JSON before score / before any future wire-up:

- injection / emergency / STOP analyzer → `requires_human` + `HANDOFF_TO_HUMAN`
- `TIME` → `TIMING`
- `END_CONTACT` must not ask a question
- Feel-Felt-Found and invented-gift phrases are replaced with the allowed target

Recorded 7B-v2 slips are covered by tests in `tests/test_companion_lora_eval.py`. Production `AI_PROVIDER` unchanged.

## Drive copy (10 September)

`rclone copy` (not NFS `cp`). First-job folder `qwen2.5-7b/` left untouched. `rclone check`: 0 differences, 4 files each for v3 and v4.

## Local mouth endpoint (10 September)

`scripts/serve_companion_mouth.py` is an OpenAI-compatible `/v1/chat/completions` wrapper. Default is dry-run. `--run` loads local 7B + **v3**. First bind used ThreadingHTTPServer and MLX raised `There is no Stream(cpu, 0)`; the server is now single-threaded `HTTPServer`. Live bind 10 Sep: `http://127.0.0.1:8741/v1/chat/completions` (owner asked). Every completion runs `mouth_guard`. Production `AI_PROVIDER` unchanged.

## Hosted GPU (Together)

Railway has no GPU. Mac mlx adapters stay on the Mac/Drive. Hosted path: same ChatML, **messages-only** JSONL at `evals/companion_step2/hosted/` and `gdrive:evorove-companion/hosted-sft/`. Owner creates the Together account and starts LoRA. Agent does not upload with an API key and does not change `AI_PROVIDER`. Guide: `evals/companion_step2/hosted/README.md`.

## Not done

- Adapter not swapped into live turns / `AI_PROVIDER`
- Knowledge cards not approved
- Together account / hosted LoRA job not started (owner must create the account)
- Live `eval_companion_lora.py --run` was not started this turn

## 7B v4 (10 September, after owner asked for another job)

Resumed v3 `adapters.safetensors` for 100 more iters into a **new** folder (v3 left intact). Local base only. `HF_HOME` was `$HOME/.cache/huggingface`, not the rclone NFS mount. `--clear-cache-threshold 2GB`. `lora_exit` 0.

| | Start val | End val | Peak mem | Path |
| --- | --- | --- | --- | --- |
| v3 (prior resume) | 0.385 | **0.265** | 5.338 GB | `private/companion-lora/adapter-qwen2.5-7b-v3/` |
| v4 (this job) | 0.417 | **0.280** | 5.338 GB | `private/companion-lora/adapter-qwen2.5-7b-v4/` |

Train loss on v4 ran ~0.02–0.06. Single-batch val is noisier than the training curve: v4 did not beat v3’s 0.265. Mouth guard still required. `AI_PROVIDER` unchanged.

Log: `reports/companion-lora-train-7b-v4-2026-09-10.log`.
