# Evorove agent instructions

- Communicate with the product owner in Russian. Product UI and customer-facing copy remain English.
- `FOUNDATION.md` is the product anchor (revised 12 September 2026, clarified 13 September 2026). Every action is checked against the three cycles and the four CRM tabs: Cold → In progress → Offer made → Done. This repository owns cycle 2 only: write cold to a person from the Cold tab and sell until close. Do not search for people here; finding lives in `evorove_lead`. The board and close live in `evorove-crm`.
- `docs/sales-agent-implementation-plan-ru.md` describes the sales-agent mechanics. It does not override `FOUNDATION.md`.
- Conversion from the first cold message to a closed deal is the product task. Do not promise a conversion rate to customers.
- The engine talks to the customer until the deal. Do not create an employee callback or hand a normal sale to a person. Missing business facts may be requested from the owner; the customer conversation stays with the engine.
- The trained AI is the configured production language model. Do not train a separate foundation model unless the owner explicitly reopens that decision.
- Read `CLAUDE.md` for the product boundaries and operational rules.
- Never run `git push`; only the owner pushes.
- Do not read, request, print, or edit secrets and local `.env` files.
- Do not add a `SalesStage` or `SalesMove` without updating the sales-agent specification and transition tests.
- Do not merge `SalesStage` into `ProcessState`: the former describes conversation progress; the latter protects business commitments.
- AI output is untrusted. Validate enums, evidence, knowledge IDs, business facts, and allowed actions in server code.
- AI may analyze language and phrase an approved move. It may not set prices, grant discounts, book unchecked slots, make guarantees, or bypass `ProcessEngine`.
- Every sales claim must be grounded in a `business_fact_id`, exact customer evidence, or an approved `knowledge_id` when a card is used. Missing knowledge cards are not a reason to hand off an otherwise diagnosable objection.
- Preserve tenant scope, consent, STOP suppression, human takeover, idempotency, concurrency controls, and durable outbox behavior.
- Keep changes inside the assigned file scope. Frontend tasks must not invent or change backend contracts.
- Run focused tests for the changed behavior before handoff. Do not weaken tests to accommodate an implementation.

