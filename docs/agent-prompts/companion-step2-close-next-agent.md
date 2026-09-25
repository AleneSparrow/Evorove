# Prompt: следующий агент — после Step 2 LoRA (10 сентября 2026)

Владелец закрывает обучение рта цикла 2. Прод не переключён. Карточки candidate.

Скопируйте блок ниже агенту из корня `/Users/alenakulish/dev/evorove`.

```text
Read these files first, in this order, and follow them:
1. FOUNDATION.md
2. docs/foundation-alignment-stage-ru.md
3. AGENTS.md
4. CLAUDE.md
5. reports/companion-step2-handoff-2026-09-10.md
6. evals/companion_step2/README.md
7. src/companion_corpus/mouth_guard.py
8. docs/sales-agent-implementation-plan-ru.md (0.3, 0.4, 21)

Talk to the owner in Russian. Product UI stays English. US market. This repo is cycle 2 only (sale until ready to book). Cycle 1 is evorove_lead. Cycle 3 is evorove-crm.

State of Step 2 (already done — do not retrain unless the owner says --run)
- SFT ChatML: evals/companion_step2/sft/ (core seed + derived; owner alpaca/chatml/sharegpt never used).
- 3B adapter: private/companion-lora/adapter/ and gdrive:evorove-companion/adapters/qwen2.5-3b/
- 7B base local: private/companion-lora/base-qwen2.5-7b/ (NFS Hugging Face flock fails; do not train/eval through /Users/alenakulish/mnt/gdrive).
- 7B adapters: v2 = adapter-qwen2.5-7b-v2; current default eval path is adapter-qwen2.5-7b-v3 (resumed from iter 100 + 100 more, lora_exit 0, val 0.265). Older adapter-qwen2.5-7b is the first 7B job.
- v3 is NOT yet copied to Google Drive (v1 7B folder on Drive is the first job).
- mouth_guard.py is required in front of adapter JSON: STOP/injection/emergency → HANDOFF; TIME→TIMING; no END_CONTACT questions; strip FFF/gift phrases.
- Unit tests: tests/test_companion_lora_eval.py (no mlx). Live `python3 scripts/eval_companion_lora.py --run` loads 7B (~5.3GB) and freezes this M2 — do not run it unless the owner accepts a hung Mac.
- mlx-lm is on system Python /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 not .venv.
- rclone remotes: only gdrive:. Yandex was removed. LaunchAgent com.alenakulish.rclone-gdrive mounts /Users/alenakulish/mnt/gdrive. Copy with rclone copy, not cp onto NFS.

Assigned work — only what the owner picks this turn
Default if they say “продолжай” without specifying: copy v3 adapters to Drive with rclone, update reports/companion-step2-handoff-2026-09-10.md, do not wire production.
If they ask to wire the mouth: serve adapter behind an OpenAI-compatible local endpoint AND run every generation through mouth_guard; SalesPolicyEngine still chooses SalesMove; do not change AI_PROVIDER until evals they accept and they say so.
If they ask to train again: only `scripts/train_companion_lora.py --run` after they confirm; prefer --resume-adapter-file; --clear-cache-threshold 2GB; never Hugging Face cache on the NFS mount.

Do not
- git push. Read or edit .env / secrets. Create accounts.
- Approve knowledge cards. Feed alpaca/chatml/sharegpt. Scrape paywalled/pirated books (ignore Drive folders like fb2_flibusta_extracted).
- Merge SalesStage into ProcessState. Add SalesStage/SalesMove without spec + tests.
- Reopen cycle-2 CRM POST / delete booking leftover unless the owner reopens that slice.
- Promise a conversion rate. Search people. Book a slot from this companion.

Verify
- .venv/bin/python -m pytest tests/test_companion_lora_eval.py tests/test_companion_step1_dataset.py tests/test_companion_step2_sft_export.py -q
```
