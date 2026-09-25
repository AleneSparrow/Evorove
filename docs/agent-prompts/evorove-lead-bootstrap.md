# Prompt: каркас репозитория evorove_lead (цикл 1)

**Основа:** `/Users/alenakulish/dev/evorove/FOUNDATION.md`  
**Карта шагов:** `/Users/alenakulish/dev/evorove/docs/three-repos-next-steps-ru.md`  
**Этап:** `/Users/alenakulish/dev/evorove/docs/foundation-alignment-stage-ru.md`

Владелец создаёт пустой репозиторий сама. Этот промпт — для агента **внутри** `/Users/alenakulish/dev/evorove_lead` (или как она его клонировала). Не создавать GitHub-репозиторий за неё. Не `git push`.

Скопируйте блок ниже агенту, указав корень нового репозитория.

```text
You are bootstrapping cycle 1 only: lead generation for Evorove.

Read first (from the sister sales repo, do not copy its app):
1. /Users/alenakulish/dev/evorove/FOUNDATION.md
2. /Users/alenakulish/dev/evorove/docs/three-repos-next-steps-ru.md
3. /Users/alenakulish/dev/evorove/docs/foundation-alignment-stage-ru.md
   (hot-lead contract is cycle 2→3, not yours)
4. /Users/alenakulish/dev/evorove/CLAUDE.md (pointer only)

Work only in /Users/alenakulish/dev/evorove_lead (this repo). If the folder is empty, that is expected. If it already has unrelated files, stop and report.

This repo is NOT a clone of evorove or evorove-crm. Do not copy Python engines, the widget, the Pulse landing, billing, sales playbook, ProcessState, SalesStage, or Docker from the sisters. CRM was copied from the engine once and inherited the wrong product. Do not repeat that.

Product
- One system, three repos: evorove_lead (find a fitting person with a reason) → evorove (sell until ready to book) → evorove-crm (book the hour).
- Cycle 1 result: a person plus a grounded reason they belong here. Not a contact dump. Not a filled CRM card. Not a booked slot.
- Cycle 1 does not message the person. Messaging is cycle 2 in evorove.
- Cycle 1 does not run objections, GREET, booking, quotes, or a chat widget.
- Audience: US SMB. Owner chat: Russian. Any future customer-facing strings: English.
- Law is not the product. No industry forks in code.

Assigned work — bootstrap only
1. Write CLAUDE.md (cycle 1 pointer + hard rules, same operational bans as sisters: no git push, no secrets, no account login).
2. Write AGENTS.md for this repo.
3. Write a short FOUNDATION.md that points to /Users/alenakulish/dev/evorove/FOUNDATION.md as the product north star and states this repo owns cycle 1 only.
4. Write README.md in English: what this repo is, what it is not, how it hands off to evorove.
5. Write docs/cycle-1-contract.md (Russian is fine for owner docs) with:
   - Input: owner-deposited business materials (their ad copy, their site URL, their service description). Owner places files; you do not scrape paywalled or third-party ads.
   - Offer/audience understanding derived from those materials. No invented price, discount, guarantee, or legal claim.
   - Output candidate: identity we may later address + required reason + source of the reason. Reject records with no reason.
   - Explicit non-goals: outreach, sales conversation, calendar, widget-as-generation.
6. Optionally a tiny Python domain module + tests for the candidate invariant (reason required). No FastAPI app, no Postgres, no LLM provider wiring, no people-search implementation in this slice.
7. .gitignore for secrets, venv, .env. Do not create .env.

Microsoft / ads
- Microsoft Ad Library API is public but EEA-impression-only (DSA). It is not the US SMB source of truth. Document it as a later optional research input, not this slice.
- Do not scrape Google Ads Transparency Center internals.
- Do not connect Bing/Google/Meta OAuth in this slice. Owner would paste credentials; that is a later step and she enters secrets herself.

Do not
- git push. Read or write .env. Create GitHub/remote. Create accounts.
- Implement people search, enrichment, email/SMS send, LinkedIn scraping, or a queue of “write to this phone”.
- Copy src/ from evorove or evorove-crm.
- Add SalesStage, ProcessState, Lemon Squeezy, Twilio, or an embeddable chat.
- Promise in README that we already find customers.
- Train a model. Approve knowledge cards. Download pirated books.

Before editing: confirm the working directory is the new repo and list files you will create.
After: report tree, what cycle 1 still cannot do, and that the owner must not treat this as live generation.

Communicate with the owner in Russian.
Do not git push.
```
