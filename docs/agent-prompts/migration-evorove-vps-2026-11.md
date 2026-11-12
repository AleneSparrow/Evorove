# Переезд Evorove с Railway на свой VPS — ноябрь 2026

> **3 ноября 2026, позже:** инфраструктура упрощается вместе с кодом — см. `docs/roadmap-axe-2026-11.md`. Для `evorove_lite` не нужны Docker, Postgres, SearxNG и Coolify: один процесс + SQLite + Litestream + Cloudflare Tunnel. Шаги про сторожа, туннель, R2, Oracle-резерв, мониторинг и сводку в Telegram — остаются в силе.

Владелец: Alena. С ней — по-русски. Решение принято 3 ноября 2026:

- **Основной сервер:** годовой KVM VPS (распродажа Black Friday, LowEndTalk), 8 ГБ RAM.
- **Запасной:** Oracle Cloud Always Free, Ampere A1 (с 15.06.2026 лимит 2 OCPU / 12 ГБ). Только тёплый резерв, не основной: Oracle может забрать простаивающий инстанс.
- **Вход и бэкапы:** Cloudflare Tunnel (адрес сервера скрыт, переключение основной ↔ запасной без смены DNS) + ночные бэкапы баз в Cloudflare R2.
- **Почта:** Zoho Mail Lite на домене evorove.com, отправка по SMTP 587 (на Railway Hobby SMTP заблокирован — главная причина переезда).
- **Что переезжает сейчас:** только Evorove — `ai-business-process-engine` (api.evorove.com + сайт), `evorove-crm`, `evorove-lead`, `searxng`, их Postgres, кроны `evorove-sweep-cron` и `evorove-lead-market-signals-cron`. n8n и остальные проекты пока остаются на Railway, решаем отдельно.

---

## Что делает владелец сама (агент этого НЕ делает)

1. **Купить VPS** (оплата — только сама). Критерии:
   - KVM (не OpenVZ/LXC), x86_64, **≥ 8 ГБ RAM, ≥ 4 vCPU, ≥ 100 ГБ NVMe**, 1 IPv4;
   - локация США (восток: Нью-Йорк / Вирджиния / Нью-Джерси) — ближе к рынку; Европа тоже допустима;
   - провайдеру **≥ 5 лет**, есть отзывы на LowEndTalk без массовых жалоб на падения;
   - **исходящий порт 587 открыт** (25 может быть закрыт — нам не нужен); спросить в тикете до покупки, если не написано;
   - есть снапшоты или хотя бы rescue/VNC-консоль;
   - цена ориентир **$40–70 за год**, продление по той же цене.
   Кандидаты, которые уже видели в 2026: ColoCrossing (8 ГБ / 4 vCPU / 80 ГБ — $39.99/год), ServerHost (8 ГБ / 120 ГБ NVMe — $59.99/год), RackNerd (Black Friday-тред). Основные распродажи — вторая половина ноября.
2. **Oracle Cloud** — завести аккаунт (Always Free, домашний регион с доступной ёмкостью A1), создать Ampere A1 **2 OCPU / 12 ГБ**, Ubuntu 24.04. Не превышать 2 OCPU / 12 ГБ: при окончании trial сверх лимита Oracle отключает **все** A1.
3. **Cloudflare** — в Zero Trust создать Tunnel `evorove`, токен выдать агенту через `.env` на сервере (агент сам токен не читает в чат). Создать R2-бакет `evorove-backups` и API-токен с доступом только к нему.
4. **Zoho Mail Lite** — ящик на evorove.com (например `hello@` или `alena@`), пароль приложения для SMTP/IMAP.
5. Выдать агенту SSH-доступ по ключу (пароль root не передавать).

---

## Задание агенту (копировать целиком)

```text
You are migrating the Evorove stack from Railway to the owner's own VPS. Talk to the owner in Russian. Read first: FOUNDATION.md, AGENTS.md, CLAUDE.md, DEPLOY.md, docs/client-zero-owner-checklist-ru.md, docs/agent-prompts/migration-evorove-vps-2026-11.md (this file).

Hard rules
- Never print, paste or commit secrets (.env, API keys, DATABASE_URL, INTERNAL_TASK_SECRET, tunnel token, R2 keys, SMTP password). Name the variable; the owner types the value into the server's .env herself.
- Do not delete anything on Railway. Railway is the rollback until the owner says to shut it down after 7 stable days.
- Do not send email to real leads during the migration. Outreach stays paused (OUTREACH paused / daily cap 0) until step 8 is signed off.
- No git push without the owner's yes. Work on a branch `infra/vps-migration`.

Step 1 — Server baseline (primary VPS)
Ubuntu 24.04 LTS. Non-root sudo user, SSH key only, password login off, fail2ban, unattended-upgrades, ufw: deny all inbound except SSH (no 80/443 — traffic comes only through Cloudflare Tunnel). Swap 4 GB. Docker + compose plugin. Timezone UTC.
Verify outbound 587 is open: `nc -vz smtp.zoho.com 587` (or the owner's Zoho DC host). If closed — stop and tell the owner.
Done when: the owner can see a short report of each hardening item and the 587 test.

Step 2 — Deploy tool
Install Coolify (self-hosted) OR keep plain docker compose — pick Coolify only if it fits in < 1 GB RAM overhead on this box; otherwise compose + a deploy script. Explain the choice in one paragraph.
Every service: `restart: unless-stopped`, healthcheck, memory limit.

Step 3 — Services
Build from the three repos (evorove, evorove-crm, evorove_lead) at the commits currently deployed on Railway (engine ab79836, crm 2970ac1, lead 27227bb). One compose project `evorove`:
- postgres (one instance, three databases: engine, crm, lead — check which Railway Postgres each service uses today: Postgres / Postgres-9WEU / Postgres-EY-2) with a named volume;
- engine (serves evorove.com SPA + api), crm, lead, searxng;
- cron container (supercronic) replacing evorove-sweep-cron (every 15 min: /internal/integrations/deliver, /internal/commercial/expire), the follow-up run, lead-searches run-due, and market-signals run-due — same schedules as Railway today;
- cloudflared (tunnel token from .env).
Internal URLs: CRM -> lead `http://lead:8002`, CRM -> engine, lead -> CRM, as in docs/client-zero-owner-checklist-ru.md. Same variable names as Railway; the owner copies values from Railway into the server .env.
Done when: all containers healthy, `curl http://engine:.../ready` OK from inside the network.

Step 4 — Data
Dump each Railway Postgres (owner runs `railway run pg_dump ...` or gives a temporary read-only connection; you give her the exact commands), restore into the VPS Postgres, compare row counts per table for staff_users, businesses, business_dna, leads, outreach_prospects, conversations, conversation_messages, billing_webhook_events. Report the counts side by side.
Done when: counts match.

Step 5 — Cloudflare Tunnel, staging hostnames first
Route `staging.evorove.com` -> engine and `staging-crm.evorove.com` -> crm through the tunnel. The owner logs in on staging, sees her board and businesses. Password reset email arrives (proves SMTP 587 works).
Done when: owner confirms login + reset email + board.

Step 6 — Backups
Nightly 03:00 UTC: pg_dump of all DBs, gzip, age/gpg-encrypted, upload to R2 `evorove-backups`, keep 14 daily + 8 weekly. Weekly restore test into a throwaway container with a row-count check; failure -> Telegram message to the owner (bot token/chat id from .env).
Done when: one backup in R2 and one successful restore test.

Step 7 — Standby on Oracle Free (ARM)
Same compose on the Oracle A1 box (images built for arm64). Postgres there restores the latest R2 backup every night (warm standby, read-only until promoted). cloudflared on standby is installed but its tunnel connector stays STOPPED. Write docs/runbook-failover-ru.md: how to switch (stop primary connector, restore latest dump, start standby connector), expected time, and how to switch back.
Keep the standby's CPU above Oracle's idle threshold only through real work (nightly restore + health checks); do not run fake load.
Done when: a failover drill is done once on staging hostnames and timed.

Step 8 — Monitoring
UptimeRobot (or Better Stack) free: evorove.com, api.evorove.com/ready, crm health, lead health — alert to the owner's Telegram/email. Plus a daily 09:00 Asia/Saigon Telegram summary from the cron container: last run of lead search (ok/fail, people found), letters sent, replies, errors in last 24h. The "search failed silently for a week" situation must be impossible.
Done when: owner receives the first summary.

Step 9 — Cutover
Lower TTLs, then point evorove.com / api.evorove.com / crm hostname to the tunnel. Lemon Squeezy webhook URL stays https://api.evorove.com/api/v1/billing/webhook (same host). Re-run the owner rehearsal from docs/client-zero-owner-checklist-ru.md on production. Only after the owner says yes: unpause outreach with OUTREACH_DAILY_CAP=20.
Rollback: switch hostnames back to Railway (left untouched) within minutes.

Step 10 — After 7 stable days
Give the owner the list of Railway services to stop and their monthly cost. She stops them herself.

Before each step say which step and which files/hosts you touch. After each step: what is done, what the owner must type herself.
```

---

## Профиль «1 ГБ» — запуск на JustHost (1 vCPU / 1 ГБ RAM / 20 ГБ NVMe, Ubuntu 24.04, Амстердам)

Решение владельца 3 ноября: сначала поднять Evorove на уже оплаченном JustHost (212.192.20.133). Замеры Railway за 7 дней (пик): engine 0.16 ГБ, crm 0.15, searxng 0.21, lead 0.09, три Postgres 0.16 — всего ~0.8 ГБ; базы на диске ~0.5 ГБ. Чтобы влезть в 1 ГБ, шаги 1–3 основного задания выполняются с такими ограничениями:

```text
Memory budget for this host (hard target): always-on containers <= 650 MB RSS total; OS + Docker <= 250 MB.

1. OS diet: remove/disable snapd, multipathd, ModemManager, unattended-upgrades' heavy timers (keep security updates via a nightly apt job), cloud-init after first boot. journald: Storage=volatile? No — persistent but SystemMaxUse=100M. Docker log driver local, max-size 10m, max-file 3.
2. Swap: 2 GB swapfile on NVMe + zram 512 MB (zstd), vm.swappiness=10, vm.vfs_cache_pressure=50. Report `free -m` before/after.
3. No Coolify (it alone needs ~1 GB). Plain docker compose + a deploy script. Images are built in GitHub Actions (linux/amd64) and pushed to GHCR; the server only pulls. Never build on this box.
4. ONE Postgres 16 instance for all three databases (engine, crm, lead), tuned: shared_buffers=64MB, effective_cache_size=256MB, work_mem=2MB, maintenance_work_mem=32MB, max_connections=25, wal_buffers=4MB, autovacuum on. Each app's SQLAlchemy pool: pool_size=3, max_overflow=2. mem_limit 160m.
5. engine and crm: uvicorn with ONE worker, no --reload, env MALLOC_ARENA_MAX=2 and PYTHONDONTWRITEBYTECODE=1. mem_limit 220m each. Measure RSS after 1 h idle and after a full rehearsal pass.
6. lead: always on (the CRM "Find people" button calls it), one worker, MALLOC_ARENA_MAX=2, mem_limit 160m. Anthropic does the page reading over HTTPS — no local model.
7. SearxNG ON DEMAND, not always on: started by lead (or by the cron wrapper) right before a search run and stopped 5 min after the last request; uwsgi workers=1, threads=2, only the engines lead actually uses (list them), mem_limit 200m. If on-demand start is not possible without changing lead code, do the code change in evorove_lead on a branch (start/stop via the Docker socket is NOT allowed — use a small sidecar "searx-gate" with a health-wait, or run searxng as a systemd socket-activated unit). Explain the chosen approach before doing it.
8. Crons: systemd timers on the host calling curl with the internal secret from a root-only env file (no extra container). Same schedules as Railway.
9. cloudflared: mem_limit 64m.
10. Backups: pg_dump runs at 03:00 UTC with nice/ionice, streamed straight to R2 (no full local copy on the 20 GB disk).
11. Acceptance: `docker stats` snapshot idle and during the owner rehearsal; zero OOM kills in `dmesg` over 72 h; p95 response of /api/v1/... board endpoint < 800 ms. If any container is OOM-killed twice, stop and tell the owner — that is the signal to move to OVH VPS-1 (2 vCPU / 4 GB, ~$4.54/mo) using the same compose, no rework.
```
