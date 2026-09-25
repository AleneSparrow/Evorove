# Prompt: companion Step 2 — local LoRA (10 September 2026)

Владелец выбрала локальную LoRA. Это рот цикла 2, не поиск и не бронь.
`SalesPolicyEngine` выбирает `SalesMove`. Прод — настроенный LLM, пока
адаптер не включён отдельно.

```text
Read FOUNDATION.md, AGENTS.md, docs/sales-agent-implementation-plan-ru.md
(0.3, 0.4, 21), evals/companion_step2/README.md,
src/companion_corpus/sft_export.py.

Assigned work
- Export: python3 scripts/export_companion_sft.py
- Dry-run: python3 scripts/train_companion_lora.py
- Job only if the owner asked --run AND mlx-lm is installed on Apple Silicon.
- Do not feed alpaca/chatml/sharegpt. Do not approve cards.
- Do not change AI_PROVIDER. Do not git push. Do not read .env.
```
