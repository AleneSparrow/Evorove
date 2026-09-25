# Prompt: следующий агент — срез D, шаг 11

**Этап:** [`docs/foundation-alignment-stage-ru.md`](../foundation-alignment-stage-ru.md)  
**Основа:** [`FOUNDATION.md`](../../FOUNDATION.md)  
**Срез:** D — **только шаг 11** (цикл 1 в `evorove_lead`). Шаг 12 не начинать.

Срезы A–C и шаг 10 закрыты. Шаг 11 **в работе**: движок и порт поиска есть, прод-источник людей не подключён.

Корень работы: `/Users/alenakulish/dev/evorove_lead`. Скопируйте блок ниже агенту оттуда (сестринские файлы читать, код продажи не копировать).

```text
Read these files first, in this order, and follow them:
1. /Users/alenakulish/dev/evorove/FOUNDATION.md
2. /Users/alenakulish/dev/evorove/docs/foundation-alignment-stage-ru.md
3. /Users/alenakulish/dev/evorove_lead/AGENTS.md
4. /Users/alenakulish/dev/evorove_lead/CLAUDE.md
5. /Users/alenakulish/dev/evorove_lead/docs/cycle-1-contract.md
6. /Users/alenakulish/dev/evorove/docs/three-repos-next-steps-ru.md
7. /Users/alenakulish/dev/evorove/src/domain/found_person.py (cycle 2 already accepts a found person; do not rewrite it)

You are executing slice D step 11 of the foundation-alignment stage. The product is three sequential cycles (generate → sell until ready to book → CRM books the hour). This repo owns cycle 1 only. Cycle 2 is /Users/alenakulish/dev/evorove. Cycle 3 is /Users/alenakulish/dev/evorove-crm.

Assigned work — only step 11
Finish cycle 1 so that from the business’s own materials we understand the offer and audience, and we can produce a list of people WITH a grounded reason. Not a contact dump. Not a widget. Not a letter.

Already true — do not reopen
- LeadGenerationEngine exists: presence → offer → PeopleSearch port → candidates + Cycle1Handoff. Default search is UnconnectedPeopleSearch (offer understood, empty list, no send). Tests use a fake connected source.
- Cycle 2 can start an outbound GREET on an already-addressable person (POST /api/v1/businesses/{business_id}/sales/outbound-first-touch): identity + reason + source + channel; explicit consent; STOP suppresses. Do not reimplement GREET here.
- Sale does not book in the same turn. CRM accepts POST /hot-leads. Do not live-wire HTTP glue between the three repos in this step.
- Offer claims must already appear in the business’s own words. No invented price, discount, guarantee, or legal claim.

Done when
- There is a real (not test-only) PeopleSearch implementation that can return people with identity + observed fact + source + addressable channel, still without scraping the open web, LinkedIn, Ad Library, or ads OAuth.
- The engine keeps only hits whose reason ties to the understood offer; a phone/email dump is rejected.
- Default / unconnected path still does not pretend to find customers.
- Tests lock: reasoned list; dump rejected; sent_messages stays empty.
- README / cycle-1 contract still do not promise that live generation already works.
- docs/foundation-alignment-stage-ru.md marks step 11 done only if the list path is real; do not mark step 12.

Suggested source for this step (prefer this over scraping)
Owner-deposited observations (files the owner placed: a public post they copied, a person they already know, a fact they can stand behind). That is still “found with a reason,” not a purchased list. Do not fetch third-party people directories. Do not connect Bing/Google/Meta. Microsoft Ad Library is EEA-only — not the US core.

Handoff shape toward cycle 2 (data only, no POST)
identity + grounded reason + source + channel we may later write on. Match the spirit of evorove src/domain/found_person.py. Do not send SMS/email from this repo.

Files you may edit (stay in evorove_lead)
- src/evorove_lead/search.py and a new owner-observation source if needed
- engine / policy / handoff / offer_reader only if the list path requires it
- tests for the connected observation source + existing engine tests
- docs/cycle-1-contract.md, README.md, AGENTS.md — honest wording only
- /Users/alenakulish/dev/evorove/docs/foundation-alignment-stage-ru.md only to mark step 11 if you actually finished it

Do not
- Step 12: companion training job, pirated corpus, approving knowledge cards.
- Message the person. Twilio, widget, SalesStage, ProcessState, booking, quotes.
- Copy src/ from evorove or evorove-crm.
- Scrape, LinkedIn, Google Ads Transparency internals, ads OAuth, secrets, .env.
- Promise in copy that search already works in production.
- Live-wire POST to evorove outbound-first-touch or CRM /hot-leads.
- git push. Create GitHub remotes. Create accounts.

Before editing: state which PeopleSearch implementation you will add and what file format the owner deposits.
After editing: run evorove_lead tests. Report files changed, whether a live web source is still unconnected, and whether step 11 can be marked done.

Communicate with the owner in Russian. Any customer-facing strings stay English.
Do not git push.
```
