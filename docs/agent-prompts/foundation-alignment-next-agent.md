# Prompt: следующий агент — срез A выравнивания с основой

**Этап:** [`docs/foundation-alignment-stage-ru.md`](../foundation-alignment-stage-ru.md)  
**Основа:** [`FOUNDATION.md`](../../FOUNDATION.md)  
**Срез:** A — шаги 0–2 (граница и правда). Не бронь, не CRM-экран, не исходящие, не генерация.

Скопируйте блок ниже агенту из корня `/Users/alenakulish/dev/evorove`.

```text
Read these files first, in this order, and follow them:
1. FOUNDATION.md
2. docs/foundation-alignment-stage-ru.md
3. AGENTS.md
4. CLAUDE.md
5. docs/sales-agent-implementation-plan-ru.md (header + sections 0–3 only until you know what you will touch)

You are executing slice A of the foundation-alignment stage. The product is three sequential cycles (generate → sell until ready to book → CRM books the hour). This repo owns cycles 1 and 2. Cycle 3 lives in /Users/alenakulish/dev/evorove-crm.

Assigned work — only this
- Step 0 is already written as the hot-lead contract in docs/foundation-alignment-stage-ru.md. Do not reopen it. Carry it into the sales-agent plan.
- Step 1: rewrite customer-facing English copy so the product is three cycles. Do not promise lead search (cycle 1 is not built). Do not keep “we do not generate leads” / “inquiries you already have” as product identity. Do not call the widget lead generation. Payment-from-end-customer honesty stays (we still do not collect that money).
- Step 2: add a short banner to docs/sales-agent-implementation-plan-ru.md that FOUNDATION.md and the stage doc override the old “inbound lead all the way to a booked deal in this engine” product frame. Keep SalesStage / SalesMove mechanics. State that sale exit is a hot lead (ready to book), not a calendar slot.

Files you may edit
- web/app/src/pages/Landing.tsx
- web/app/src/pages/LawyersLanding.tsx (Wave 1 entry is allowed; do not make lawyers the product; do not claim generation)
- web/app/src/content/faq.ts
- web/app/src/content/legal.ts (and legal.test.ts if assertions mention inbound-only / no-generation identity)
- docs/sales-agent-implementation-plan-ru.md (banner + any sentence that equates sale with booking in this repo)
- docs/foundation-alignment-stage-ru.md only to mark slice A progress if you actually finished a step — do not rewrite the contract

Do not
- Change Python, migrations, enums, ProcessEngine, SalesPolicyEngine, commercial.initialize, widget.js behavior, or evorove-crm.
- Start cycle 1, outbound first-touch, companion training, knowledge-card approval, or a booking/dashboard rewrite.
- Invent a new SalesStage or SalesMove.
- Promise a conversion rate. Promise that search already works. Promise that the widget finds people.
- git push. Read or edit .env / secrets. Create accounts.
- Weaken tests. If a legal/faq test encodes the old inbound-only identity, update the test to the new honest copy, do not delete coverage.

Copy rules (English, US)
- Owner evening picture: tomorrow’s appointments in CRM — as the destination of the system, not a live feature to fake.
- Cycle 2 (this product now): the agent talks until the person is ready to book. Incoming chat/SMS remain a channel, not the whole product.
- Cycle 1: named as the next contour, not shipped.
- Cycle 3: booking an already-hot person; not “we are a CRM”.
- Tone: alive, SMB, not enterprise, not a form. No dry “ready-made sales cycle” that still means inbound-only intake.
- Lawyers page: still CA/NY wedge, still not “a product for lawyers”, still inquiry channel for now, no fake generation.

Before editing: list the exact strings you will change and how they map to cycles 1/2/3.
After editing: run the focused frontend tests that cover copy (legal.test.ts, any faq tests). Report files changed, what you did not do, and whether slice A can be marked done.

Communicate with the owner in Russian. Customer-facing strings stay English.
Do not git push.
```
