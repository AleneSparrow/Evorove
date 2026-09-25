# Prompt: следующий агент — срез D, шаг 10

**Этап:** [`docs/foundation-alignment-stage-ru.md`](../foundation-alignment-stage-ru.md)  
**Основа:** [`FOUNDATION.md`](../../FOUNDATION.md)  
**Срез:** D — **только шаг 10** (исходящий первый ход в цикле 2). Шаги 11 и 12 не начинать.

Срезы A–C закрыты 7 сентября 2026. Копируйте блок ниже агенту из корня `/Users/alenakulish/dev/evorove`.

```text
Read these files first, in this order, and follow them:
1. FOUNDATION.md
2. docs/foundation-alignment-stage-ru.md
3. AGENTS.md
4. CLAUDE.md
5. docs/sales-agent-implementation-plan-ru.md (header + 0–3, then only sections you will touch)
6. src/domain/hot_lead_handoff.py (cycle 2→3 payload exists; do not POST it yet)
7. docs/three-repos-next-steps-ru.md (handoff 1→2: found person + reason + source + addressable channel)

You are executing slice D step 10 of the foundation-alignment stage. The product is three sequential cycles (generate → sell until ready to book → CRM books the hour). This repo owns cycle 2. Cycle 1 is /Users/alenakulish/dev/evorove_lead. Cycle 3 is /Users/alenakulish/dev/evorove-crm.

Assigned work — only step 10
The engine must write first to a found person. GREET must not assume they wrote in (“thanks for reaching out”, “you reached out”, “got your message”). Consent / TCPA / STOP for this first outbound touch must be stricter than the inbound widget: no inferred consent, no send without an explicit allowed basis, STOP still ends contact.

Done when:
- There is a server path that starts a sales conversation on an already-addressable person (phone and/or email) without a prior inbound customer message.
- The first customer-facing line is a live GREET about the business offer / their situation, not inbound-intake phrasing.
- A test proves: outbound GREET does not contain “thanks for reaching out” / “you reached out”; missing consent blocks the send; STOP still suppresses.
- SalesPolicyEngine still chooses GREET_AND_SET_CONTEXT (or the existing GREET move). Do not invent a new SalesStage or SalesMove unless the sales-agent spec and transition tests are updated in the same change — prefer reusing GREET.

Context already true — do not reopen
- Sale does not book: OFFER_BOOKING_SLOTS sets ready-to-book / QUALIFIED and does not call commercial.initialize in that turn.
- Discovery is problem + outcome, not ZIP/forms.
- Widget is an inbound channel, not generation.
- CRM already accepts POST /hot-leads and shows tomorrow’s appointments. Do not live-wire the HTTP glue. Do not delete booking leftover from this repo.
- src/domain/hot_lead_handoff.py only shapes the 2→3 payload. Leave it.

Handoff 1→2 (input to this step)
Accept a found person as data, even if cycle 1 is not searching yet: identity + grounded reason + source + channel we may write on. Reject a contact dump with no reason. Do not implement people search here.

Files you may edit (stay inside cycle 2)
- src/engine/sales_policy.py, src/engine/sales_live_turn.py, src/ai/sales_prompts.py, src/ai/sales_response_prompts.py (and version constants if prompts change)
- persistence / API needed to start an outbound first touch (new route or service is allowed if it preserves tenant, consent, STOP, idempotency)
- tests that lock outbound GREET + consent/STOP
- docs/sales-agent-implementation-plan-ru.md only if a sentence still assumes every GREET is inbound
- docs/foundation-alignment-stage-ru.md only to mark step 10 done if you actually finished it — do not rewrite the hot-lead contract

Do not
- Step 11: people search, scraping, Ad Library, outreach queues, evorove_lead production search.
- Step 12: companion training job, pirated corpus, approving knowledge cards.
- evorove-crm changes. Do not POST hot leads. Do not delete commercial booking from this repo.
- New SalesStage / SalesMove without updating the spec and transition tests.
- Merge SalesStage into ProcessState.
- Hand a normal sale to a human. Promise a conversion rate. Promise that search already works.
- git push. Read or edit .env / secrets. Create accounts. Weaken tests.

Tone (English, US, customer-facing)
Alive, SMB, not a form or a call center. Outbound GREET is a first hello from the business, not “thanks for writing”. Fallback must not be inbound-only.

Before editing: list the exact entrypoint (who calls GREET with no inbound message) and how consent is checked.
After editing: run focused tests for the new outbound path plus existing sales-live / sales-policy tests. Report files changed, what you did not do, and whether step 10 can be marked done. Do not mark steps 11–12.

Communicate with the owner in Russian. Customer-facing strings stay English.
Do not git push.
```
