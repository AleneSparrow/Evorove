# Задания агентам — 3 ноября 2026

> **Заменено 3 ноября 2026:** проект пересобирается как `evorove_lite` — см. `docs/roadmap-axe-2026-11.md` и `docs/agent-prompts/axe/`. Задачи ниже в старых репозиториях НЕ выполнять. Исключение по желанию владельца: срочная заплатка вебхука Lemon Squeezy (Агент 1, задача A) в старом `evorove`, если тестовые оплаты чужих людей надо закрыть до запуска топора.

Три задания, по одному на репозиторий, чтобы агенты не мешали друг другу.
Каждый блок копируется агенту целиком. Общение с тобой у агентов на русском, код и тексты для клиентов на английском.

Общие правила (они уже вписаны в каждый блок):
- никакого `git push` и мержа без твоего «да»; агент работает в своей ветке и показывает diff
- `.env`, ключи, `DATABASE_URL`, `INTERNAL_TASK_SECRET` не читать, не печатать, не менять: агент называет переменную, значение вводишь ты
- тесты не ослаблять

---

## Агент 1 — Codex → репозиторий `evorove` (движок продаж + billing)

```text
Repo: /Users/alenakulish/dev/evorove. Talk to the owner in Russian. Code and customer-facing strings in English. US B2B market.
Read first: FOUNDATION.md, AGENTS.md, CLAUDE.md, docs/client-zero-owner-checklist-ru.md.

Hard rules: no git push, no merge. Work on a new branch. Never read or print .env, API keys, DATABASE_URL, INTERNAL_TASK_SECRET — name the variable, the owner types the value. Do not weaken tests.

Problem (seen in production logs on 2 Nov 2026): Lemon Squeezy is in test mode on purpose (the product is not ready for real money). A stranger signed up on evorove.com, paid $199 "Atelier Starter" with the test card 4242, and POST /api/v1/billing/webhook returned 200 and activated the plan. BillingService.handle_webhook never looks at meta.test_mode, so anyone gets a paid plan for free.

Task A — test-mode payments only for the owner's test account.
1. New setting BILLING_TEST_MODE_ALLOWED_EMAILS (comma-separated, case-insensitive, default empty) in src/config.py, documented in .env.example and DEPLOY.md.
2. In BillingService.handle_webhook: if meta.test_mode is true and the business owner's email (the staff user that owns the business from custom_data.business_id) is NOT in that list -> record the event as ignored (log event "billing_test_mode_event_ignored" with business_id and event_name, no PII beyond that), do not change plan or subscription_status, return 200 so Lemon Squeezy stops retrying.
3. If meta.test_mode is true and the owner IS on the list -> process as today.
4. Live-mode events (test_mode false/absent) -> unchanged.
Done when: tests cover all three branches, including a stranger with test_mode=true staying on subscription_status "incomplete".

Task B — clean up what already leaked.
Write a one-off read-only script scripts/list_test_mode_subscriptions.py that prints businesses whose plan was activated by a test-mode webhook event (join billing_webhook_events), with business id, name, owner email, created_at. Then a second script, separate, that downgrades a given list of business ids to subscription_status "incomplete" and plan NULL — it must take ids as explicit arguments and have a --dry-run default. Do not run either against production yourself; hand the owner the commands.

Task C — the owner's dedicated test admin account.
The owner needs ONE separate login used only for walking the customer path (sign up -> onboarding -> checkout with test card -> board -> first letter -> reply -> offer -> Done), separate from her real account.
1. Add scripts/provision_owner_test_account.py: creates (idempotently) a staff user with the email given as an argument, a business named "Evorove QA (owner test)" with test_mode_enabled = true, and prints the business_id. Password is NOT generated or printed by the script: it triggers the existing password-reset email so the owner sets the password herself.
2. Add --reset flag: wipes that one business's leads, conversations, outreach_prospects, process_cases, sales_turns, bookings, quotes, payment_requests and statistics so the path can be walked again. It must refuse to run on any business whose test_mode_enabled is false.
3. That email goes into BILLING_TEST_MODE_ALLOWED_EMAILS (Task A).
Done when: tests show provisioning is idempotent and --reset refuses a non-test business.

Before editing, say which task you are on and which files you will touch. After each task, say what is done and which variables the owner must set herself. Run focused tests only.
```

---

## Агент 2 — Cursor → репозиторий `evorove-crm` (доска + запуск поиска)

```text
Repo: /Users/alenakulish/dev/evorove-crm. Talk to the owner in Russian. Code and UI strings in English.
Read first: FOUNDATION.md, AGENTS.md, CLAUDE.md, docs/lead-touch-contract.md.

Hard rules: no git push, no merge. Work on a new branch. Never read or print .env, keys, DATABASE_URL, INTERNAL_TASK_SECRET. Do not weaken tests.

Problem (production logs, every day since at least 27 Oct 2026): POST /api/v1/internal/lead-searches/run-due fails with
  WARNING lead_search_unreachable error=<urlopen error [Errno 111] Connection refused>
  -> 502 lead_search_unavailable
So Cold never fills, no letters go out, the board is silent, and nobody noticed for a week. The working internal address of the lead service on Railway is http://evorove-lead.railway.internal:8002 (the market-signals cron reaches it fine). The owner's CRM variable EVOROVE_LEAD_BASE_URL is being corrected separately on Railway — you do not touch Railway.

Task A — fail loudly, not silently.
1. On CRM startup, if EVOROVE_LEAD_BASE_URL is set, probe <base>/health (short timeout). Log one clear line "lead_search_base_url_unreachable" with the host:port (never the secret) if it fails. Do not crash the CRM.
2. Add GET /api/v1/internal/health/dependencies (gated by INTERNAL_TASK_SECRET) returning reachable true/false + latency for the lead service and the sale engine.
3. On the /app board, when the last run-due for this business failed, show one plain line above Cold: "Search did not run: lead service unreachable since <time>." No buttons.
Done when: tests cover the probe failing and succeeding, and the board line appears only after a failed run.

Task B — prove the Cold handoff end to end against a stub.
A test that starts a stub lead service, calls run-due, receives a grounded person with email + reason + segment, and asserts a Cold lead-touch appears on /app for the client-zero business_id. A person without a reason is dropped.

Before editing, say which task you are on and which files you will touch. Run focused tests only.
```

---

## Агент 3 — Grok → репозиторий `evorove_lead` (кого мы ищем)

```text
Repo: /Users/alenakulish/dev/evorove_lead. Talk to the owner in Russian. Code in English. Market: US B2B. Client 0 is Evorove itself selling its own subscription.
Read first: FOUNDATION.md, AGENTS.md, CLAUDE.md, docs/cycle-1-contract.md, docs/client-zero-pilot-checklist-ru.md, owner-materials/.

Hard rules: no git push, no merge, new branch. Never read or print .env, ANTHROPIC_API_KEY, DATABASE_URL, INTERNAL_TASK_SECRET. This repo never sends a message. Do not scrape paywalled or pirated sources. Do not weaken tests.

Goal: before any letter goes to a stranger, the owner must SEE who the search would put on Cold, and judge it.

Task A — dry run.
Add POST /api/v1/internal/searches/dry-run (gated by INTERNAL_TASK_SECRET) and a CLI `python -m evorove_lead.client_zero --dry-run --limit 20`. It runs the full client-0 pipeline (brief -> hypotheses -> SearxNG -> Anthropic reading -> re-selection) but does NOT post to CRM and does NOT write to the delivery outbox. Output JSON + a Markdown table: company, website, US state, person name and role, email (domain only in logs), the grounded pain/reason with its verbatim evidence quote and source URL, segment, hypothesis id, and why it passed fit.
Done when: a test proves dry-run never calls the CRM client or the outbox.

Task B — cost guard.
Count Anthropic input/output tokens per run (from the API response usage) and log one line per run: "lead_run_token_usage" with totals and number of pages read. Add MAX_ANTHROPIC_TOKENS_PER_RUN (default 300000): when reached, the run stops cleanly and logs why. Daily runs must never silently burn millions of tokens.

Task C — US B2B targeting check.
Review the client-0 brief and hypotheses against this: buyers are US small and mid-size B2B service businesses with a sales process (agencies, consultancies, B2B services, home-services companies selling to other businesses) whose owner or head of sales is reachable by a business email published on the company's own site. Report in Russian which hypotheses fit, which do not, and what you would change — without changing the brief text yourself; the owner decides.

Before editing, say which task you are on and which files you will touch. Run focused tests only.
```

---

## Агент 1 (Codex), задача D — ОТЛОЖЕНА (не делать)

> 3 ноября решили: Evorove переезжает на свой VPS, где порт 587 открыт. Отправка остаётся через SMTP (Zoho Mail Lite). Задача D нужна только если на выбранном VPS окажется закрыт 587.

### Исходный текст задачи D (для справки)

```text
Same repo and hard rules as above.

Problem: production runs on Railway Hobby, which blocks outbound SMTP (ports 25/465/587). Every SMTP send times out after 10 s and is silently swallowed: password-reset emails never arrive (seen 3 Nov 2026: /api/v1/auth/forgot-password took 10.1 s, no mail), and cold outreach from the connected mailbox cannot leave either. The owner will not upgrade Railway. The sending mailbox will be Zoho Mail (Mail Lite) on the evorove domain; DNS stays on Cloudflare. IMAP (port 993) for reading replies is not blocked and stays as is.

Task D:
1. Add an outbound-mail adapter that sends through the Zoho Mail REST API over HTTPS (OAuth2 refresh-token flow; Zoho data-center base URL configurable, e.g. mail.zoho.com / mail.zoho.eu). One interface used by BOTH the password-reset sender and outreach/follow-up sending. Keep the SMTP adapter; choose with MAIL_TRANSPORT=smtp|zoho_api (default smtp so tests and local stack stay unchanged).
2. New settings, documented in .env.example and DEPLOY.md, values typed by the owner only: ZOHO_MAIL_CLIENT_ID, ZOHO_MAIL_CLIENT_SECRET, ZOHO_MAIL_REFRESH_TOKEN, ZOHO_MAIL_ACCOUNT_ID, ZOHO_MAIL_API_BASE. Write the owner a step-by-step in Russian (docs/zoho-mail-setup-ru.md): create the Zoho self-client, scopes needed for sending, how to get the refresh token, SPF/DKIM/DMARC records to add in Cloudflare DNS.
3. Failures must be visible: log one line "outbound_mail_failed" with transport, error class and HTTP status — never the recipient, body, token or reset URL. Password reset still returns the same generic 202 to the caller.
4. Keep every existing outreach guard: unsubscribe link, postal address, quiet hours, suppression list, daily cap. Add OUTREACH_DAILY_CAP default 20 for a new mailbox (warm-up).
Done when: tests cover the Zoho adapter with a stubbed HTTP client (success, 401 token refresh, 4xx/5xx failure logged), and both password reset and the first cold letter go through the selected transport.
