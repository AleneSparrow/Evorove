# Local companion LoRA adapters (Step 2)

Gitignored except this README. Drop purchased books stay in `../sales-corpus/`.

`python3 scripts/train_companion_lora.py` is dry-run by default.
`python3 scripts/train_companion_lora.py --run` writes adapters here and still does
not change production `AI_PROVIDER`.

On 10 September 2026:

- `adapter/` — Qwen2.5-3B-Instruct-4bit LoRA
- `adapter-qwen2.5-7b/` — first Qwen2.5-7B-Instruct-4bit LoRA job
- `adapter-qwen2.5-7b-v2/` — second 7B job
- `adapter-qwen2.5-7b-v3/` — resume from iter 100; val 0.265
- `adapter-qwen2.5-7b-v4/` — resume from v3 for 100 more iters; val 0.280
- `base-qwen2.5-7b/` — local copy of the 7B 4bit base (from Drive; do not git it)
