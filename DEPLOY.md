# Deploying Evorove to production

One product, one Railway project, one site. The owner opens
[https://evorove.com](https://evorove.com). The API is
[https://api.evorove.com](https://api.evorove.com). The Docker image builds
the React app and the API serves it. There is no public CRM hostname and no
separate Vercel frontend.

The backend already has a `Dockerfile`, Alembic migrations before each
deploy, and `/health`. This guide is account setup and environment
variables. The owner types secrets. The agent does not.

## 1. Backend on Railway

1. Sign up at railway.com (GitHub login is the fastest option) and create a
   **New Project → Deploy from GitHub repo**, pointing at this repository.
   Railway will detect the `Dockerfile` automatically. Keep cycle 1 and the
   board journal in **this same project** if they run as extra services.
2. In the same project, click **+ New → Database → PostgreSQL**. Railway
   provisions it and exposes a `DATABASE_URL`-shaped set of variables
   automatically inside the project.
3. On the backend service, open **Variables** and set:
   - `DATABASE_URL` — reference the Postgres plugin's connection string
     (Railway lets you paste a variable reference like
     `${{Postgres.DATABASE_URL}}`, but the value must be in this app's
     expected driver format: `postgresql+psycopg://...` — if Railway's
     Postgres plugin variable comes as a plain `postgresql://...` URL,
     change the scheme prefix to `postgresql+psycopg://` before saving).
   - `APP_ENV` = `production`
   - `AI_PROVIDER` = `deterministic` to launch without any AI dependency at
     all (qualification and booking are deterministic either way; this only
     turns off AI-assisted intake wording), or `anthropic`/`openai` if you
     want AI-assisted wording — if `anthropic`, also set `ANTHROPIC_API_KEY`
     and `ANTHROPIC_MODEL`; if `openai`, set `OPENAI_API_KEY` and
     `OPENAI_MODEL` instead. Optional `OPENAI_BASE_URL` points the OpenAI
     adapter at Groq, Together, or another OpenAI-compatible API. With
     `AI_PROVIDER=anthropic`, the same `OPENAI_*` values are an optional
     second cloud: Anthropic outage continues the same constrained request
     there before deterministic fallback. Set keys **directly in
     Railway's Variables tab**, not by giving them to Claude.
   - `CORS_ALLOWED_ORIGINS` — `https://evorove.com`. The app refuses a
     wildcard (`*`) in production.
   - `FRONTEND_BASE_URL` — `https://evorove.com` (no trailing slash).
   - `PUBLIC_API_BASE_URL` — `https://api.evorove.com` (unsubscribe links).
   - `CRM_BASE_URL` — internal origin of the board journal in this project,
     not a second public site.
   - `LOG_LEVEL` = `INFO` (optional, this is already the default)
4. Deploy. Railway builds the Docker image, runs `alembic upgrade head` once
   as a pre-deploy step, then starts the app (see `railway.toml` — this is
   automatic, nothing to run by hand). Migrations deliberately run there and
   not inside the container's start command: as a pre-deploy step they run
   exactly once per deployment, before anything serves traffic, so adding a
   second replica later can't make several containers race to apply the same
   migration. Once it's live, Railway shows a public URL like
   `https://your-service.up.railway.app`. Custom domains: `api.evorove.com`
   and `evorove.com` on this image.

## 2. Billing (Lemon Squeezy) — required before a real customer can subscribe

Self-serve billing (`src/persistence/billing_service.py`) is fully built and
wired in, but it's off until you do the account-side setup below — with no
`LEMONSQUEEZY_API_KEY` set, the backend boots fine and everything else works,
but billing endpoints return a clear "not configured" error instead of a
crash. Account creation and entering the secret keys are things only you can
do.

Runs on **Lemon Squeezy**, not Stripe — Stripe's supported-country list
doesn't include Vietnam. Lemon Squeezy is a Merchant of Record (it's the
legal seller on every transaction and handles sales-tax/VAT compliance
itself), and it explicitly supports Vietnam-based sellers for payouts. The
fee is higher than Stripe's (5% + $0.50/transaction vs. Stripe's ~2.9% +
$0.30) — a deliberate tradeoff for Vietnam eligibility plus not having to
handle tax compliance yourself.

1. Sign up at [lemonsqueezy.com](https://lemonsqueezy.com) and create a
   **Store** (Settings → Stores) — this is where you'll set your payout bank
   account (Vietnamese bank account works here). New stores start in **Test
   mode** (a toggle in Store settings) so you can go through the whole flow
   below before charging real cards.
2. **Products → New product**, twice:
   - **Starter** — subscription, **$199.00/month**.
   - **Pro** — subscription, **$499.00/month**.
   For each product's variant, open **Subscription options** and set the
   **free trial** to **7 days** — this is configured here in the dashboard,
   not passed by the app per-checkout (unlike Stripe). If you ever change
   this number, also update `BILLING_TRIAL_DAYS` below and the "Start 7-day
   free trial" copy in `web/app/src/pages/Billing.tsx` — the app doesn't
   read the trial length back from Lemon Squeezy, it's copy-only there.
   Copy each variant's **Variant ID** (visible in the product's URL or via
   **Store → Products → (product) → Variants**) — you'll need both in step 3.
3. On the Railway backend service, add these Variables:
   - `LEMONSQUEEZY_API_KEY` — **Settings → API** in Lemon Squeezy → **Create
     API key**. Goes directly into Railway, same as `OPENAI_API_KEY`.
   - `LEMONSQUEEZY_STORE_ID` — **Settings → Stores**, shown next to your
     store name.
   - `LEMONSQUEEZY_VARIANT_STARTER` / `LEMONSQUEEZY_VARIANT_PRO` — the two
     Variant IDs from step 2.
   - `FRONTEND_BASE_URL` — `https://evorove.com` (no trailing slash). Lemon
     Squeezy Checkout redirects back here after payment.
   - `BILLING_TRIAL_DAYS` — optional, defaults to `7`; keep in sync with
     step 2's dashboard setting (copy-only, doesn't control anything).
   - `LEMONSQUEEZY_WEBHOOK_SECRET` — from step 4 below (you'll come back to
     this).
4. **Settings → Webhooks → Add webhook** in Lemon Squeezy:
   - Callback URL: `https://api.evorove.com/api/v1/billing/webhook`
   - Signing secret: type in your own secret string here (Lemon Squeezy
     doesn't generate one for you like Stripe does) — then set that same
     value as `LEMONSQUEEZY_WEBHOOK_SECRET` in Railway (step 3) and
     redeploy.
   - Events to send — select exactly these eight (the app ignores everything
     else, but only select what you need):
     `subscription_created`, `subscription_updated`,
     `subscription_cancelled`, `subscription_resumed`,
     `subscription_expired`, `subscription_paused`,
     `subscription_unpaused`, `subscription_payment_failed`.
5. Smoke test billing specifically: sign up a test account through your live
   frontend, go through onboarding, land on **Billing**, pick a plan, and
   complete Checkout while the store is still in **Test mode** (Lemon
   Squeezy's [testing docs](https://docs.lemonsqueezy.com/help/getting-started/test-mode)
   cover the test card to use). You should land back on `/app/billing` and
   the dashboard should unlock within a few seconds (it's waiting on the
   webhook, not the redirect, to actually flip the switch). Once you're
   confident it works, flip the store out of Test mode in Lemon Squeezy
   before sending it to real customers.

## 3. Smoke test

On the live site, not on localhost:
- Open https://evorove.com, sign in, confirm `/app` loads.
- Open https://api.evorove.com/health and `/ready` — both should return `200`.
- If the browser cannot reach the API, `CORS_ALLOWED_ORIGINS` must be exactly
  `https://evorove.com`.

## 4. Proactive follow-up SMS (optional)

Re-contacts a stalled lead (never replied, still `NEW_LEAD`/`CONTACTED`/
`QUALIFYING`) after the delays configured in Business DNA's
`sales.follow_up` (24h/72h/168h by default, up to 3 attempts). Requires SMS
already set up (a business has provisioned a Twilio number from Settings)
and, per lead, an explicit consent checkbox ticked in the widget -- no
consent, no follow-up, ever (see `src/domain/models.py`'s `Lead.sms_consent`
docstring). Skip this whole section if you don't want proactive follow-up
yet; nothing else in the deploy depends on it.

1. On the backend service, set `INTERNAL_TASK_SECRET` to a long random
   value (e.g. `openssl rand -hex 32`) in Railway's Variables tab. Leaving
   it unset disables the endpoint entirely -- it refuses every request
   rather than running unauthenticated.
2. In the same Railway project, **+ New → Cron Job** (or **Empty Service**
   configured as a scheduled job, depending on what your Railway plan
   offers). Point it at the backend service's public URL and have it run,
   on whatever cadence you want checked (hourly is reasonable given the
   24h/72h/168h defaults):
   ```
   curl -X POST https://api.evorove.com/api/v1/internal/follow-up/run \
     -H "X-Internal-Task-Secret: <the same value as INTERNAL_TASK_SECRET>"
   ```
   The same secret also gates two other sweeps added with migration `0020`.
   Run them on the same hourly (or slower) cadence, or by hand:
   ```
   curl -X POST https://api.evorove.com/api/v1/internal/integrations/deliver \
     -H "X-Internal-Task-Secret: <the same value as INTERNAL_TASK_SECRET>"

   curl -X POST https://api.evorove.com/api/v1/internal/commercial/expire \
     -H "X-Internal-Task-Secret: <the same value as INTERNAL_TASK_SECRET>"
   ```
   CRM journal Found cards are ingested (cycle 2 writes GREET) with the same
   secret; contract: `docs/cycle-2-found-ingest-contract.md`.
   Set `CRM_BASE_URL` to the board journal's internal origin in this Railway
   project. That is not a second public site. Cycle 2 does not send a calendar
   hour. Use the same `INTERNAL_TASK_SECRET`.
   ```
   curl -X POST https://api.evorove.com/api/v1/internal/businesses/<business_id>/found \
     -H "X-Internal-Task-Secret: <the same value as INTERNAL_TASK_SECRET>" \
     -H "Content-Type: application/json" \
     -d '{"person_id":"ppl_example","reason":"Asked neighbors this week for help with a broken AC","source":"open-web","channel":"sms","consent_basis":"prior_express_written","identity":{"phone":"+15551234567"}}'
   ```
   `integrations/deliver` retries CRM webhook outbox rows and conversational
   SMS replies. `commercial/expire`
   expires stale quotes and payment requests that nobody has messaged since
   they became due.
3. You can also just call it by hand any time (same curl command) to run a
   sweep immediately instead of waiting for the schedule.

Deliberately NOT an automatic in-process background loop -- see
`src/persistence/follow_up_service.py`'s module docstring for why (mainly:
it stays safe to trigger from more than one place, or scale to more than
one replica, without double-sending).

**Not yet done, before this should carry real customer traffic:** the
widget's consent checkbox text (`web/widget/widget.js`) is a placeholder
shape, not reviewed by a lawyer -- see the delivery notes for this feature.
Inbound SMS `STOP` / `START` / `HELP` are honored on the Twilio number.
Also, only the website chat widget captures follow-up consent right now; a
lead that only ever came in over inbound SMS or the direct API has no
follow-up consent-capture path yet and will simply never qualify for
proactive follow-up (safe by default, just incomplete coverage). Conversation
replies to a number that texted in still go out until that person sends STOP.

## 5. Google Calendar connection (optional, for offline closes)

An offline close is a real hour in the business's own calendar
(`FOUNDATION.md`); until the owner connects a calendar, a booked hour in a
"foreign" calendar does not count as placed. This is entirely optional: with
the variables below unset the feature is off — no connection UI, no event
writes — and every online (payment-link) close works unchanged.

1. Register a Google OAuth web application at
   `console.cloud.google.com/apis/credentials` (the owner does this herself;
   do not create the app or share its secret):
   - Application type: **Web application**.
   - Authorized redirect URI: `https://evorove.com/app/settings?tab=calendar`.
   - Add the scope `https://www.googleapis.com/auth/calendar.events` (write-only;
     the engine never reads or lists the owner's calendar).
   - Publish the app for testing or production as Google requires.
2. On the backend service set:
   - `GOOGLE_CALENDAR_CLIENT_ID` — the OAuth client ID.
   - `GOOGLE_CALENDAR_CLIENT_SECRET` — the OAuth client secret.
   - `ACCOUNT_SECURITY_ENCRYPTION_KEY` — at least 32 characters of high-entropy
     material (the same key already used for authenticator-app 2FA). Both
     Google tokens are stored Fernet-encrypted with it; the database never
     sees a plaintext token.
3. The owner then opens **Settings → Calendar** and clicks
   **Connect Google Calendar**. Google consents with `prompt=consent` +
   `access_type=offline`, so a refresh token is issued and the connection
   stays alive past the first hour.
4. Delivery rides the same `integrations/deliver` sweep as the CRM board
   (step 6.2 above), so the hour lands even if a write fails and is retried
   with the usual 8-attempt / 5-minute-linear backoff. A reschedule PATCHes
   the existing event; a cancel deletes it.

## Known limitation carried over from local dev

The public chat and account-security rate limiter (`src/api/rate_limit.py`)
is shared across workers via the `rate_limit_hits` table (migration `0020`).
A second Railway replica is therefore no longer blocked on abuse control.
Calendar sync for the tenant's own Google/Outlook calendar, and collection
of money from the tenant's end customer, remain deferred.
Migrations used to race when they ran inside every container's start
command. They now run once, as `preDeployCommand` in `railway.toml`.
