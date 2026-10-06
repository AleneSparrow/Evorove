# Prompt: запуск клиента 0 (5 октября 2026)

Владелец: Alena. Общение с ней — русский. Клиентские тексты — английский. Рынок — США.

Это задание на **один замкнутый проход клиента 0**: Evorove продаёт свою подписку. Чужой бизнес не подключать, пока этот проход виден на одной доске от Cold до Done.

Скопируйте блок ниже агенту. Корень работы — `/Users/alenakulish/dev/evorove`. Соседние репозитории трогать только в шагах, где это сказано.

Отчёт, из которого взят порядок: разбор 5 октября 2026 (три репозитория, локальный стек `evorove/system`, прод `api.evorove.com` и CRM на Railway).

---

```text
You are closing the client-0 loop for Evorove. Client 0 is Evorove selling its own subscription. Do not onboard a second business.

Talk to the owner in Russian. Product UI and every customer-facing string stay English. US market.

Read first, in order:
1. /Users/alenakulish/dev/evorove/FOUNDATION.md
2. /Users/alenakulish/dev/evorove/AGENTS.md
3. /Users/alenakulish/dev/evorove/CLAUDE.md
4. /Users/alenakulish/dev/evorove/docs/agent-prompts/client-zero-launch-next-agent.md
5. /Users/alenakulish/dev/evorove_lead/docs/cycle-1-contract.md
6. /Users/alenakulish/dev/evorove-crm/docs/lead-touch-contract.md

Repos, do not mix their jobs:
- /Users/alenakulish/dev/evorove_lead — cycle 1. Brief, Anthropic reading, SearxNG pages, re-selection, Cold handoff. Does not send a message.
- /Users/alenakulish/dev/evorove — cycle 2. First email and the sale. Does not search the web. Does not book a slot in the same turn.
- /Users/alenakulish/dev/evorove-crm — board and close. Does not scrape. Does not start GREET.

Hard rules
- Never git push. Commit only if the owner asks in this chat.
- Never read, print, or edit .env, API keys, DATABASE_URL, or INTERNAL_TASK_SECRET. Name the variable the owner must set. She types the value.
- Do not log into accounts or create them.
- Do not change AI_PROVIDER to the companion LoRA. The 25 Sep seed eval passed 17 of 35. The book-trained mouth stays off until a per-move eval passes and the owner says to switch. The production model phrases the move. SalesPolicyEngine still chooses the move.
- Do not start a training job. Do not approve knowledge cards. Do not scrape paywalled or pirated books.
- Do not weaken tests. AI output is untrusted: validate enums, evidence, and allowed actions in server code.
- No invented price, discount, guarantee, or slot. Gender and region are shown only when already recorded. Do not infer them from a name.
- Cold contacts are never texted. SMS stays blocked.
- A normal sale is not handed to a person. STOP, emergency, and policy stops stay on the Safety page. They are not buttons on the watch board.

What is already true — do not rebuild it
- Four tabs exist: Cold, In progress, Offer made, Done. A lead-touch moves the tab. Drafts do not.
- Landing, FAQ, Account, Billing, Statistics, and Materials with Refresh already exist on evorove.com.
- api.evorove.com and the CRM Railway service answered ready on 5 Oct 2026.
- Local stack evorove/system has been up since 1 Oct: engine :8001, crm :8000, lead :8002. That lead container has no WEB_SEARCH_BASE_URL and no Anthropic key. A separate SearxNG listens on :8080 and is not wired to that stack.
- system/run-e2e.sh walks a fixture person. A green run is not client 0.
- On 17 Sep a live client-0 search found 8 people and did not POST them to CRM.

Current code the work has to change
- Two boards. /app (Dashboard.tsx, crmBoard.ts) maps ProcessState. /app/people (Board.tsx) is the lead-touch journal and still has discard, pause, and takeover.
- First email is draft_first_email in src/persistence/outreach_service.py: a fixed template plus the cycle-1 reason. Approve exists as POST .../outreach/prospects/{id}/approve. There is no screen for it. The owner’s launch rule is: the engine sends. She watches. She does not approve each letter and does not hop in to close.
- Cycle 1 already reads with Anthropic when AI_PROVIDER=anthropic: marketing_analysis.py (4P and 2–3 segments, verbatim quotes), decision_maker_llm.py, market_signal_llm.py. SearxNG only fetches pages (web_search.py). Those segments are not inputs to the first email.
- legal.ts still says finding people is not part of the service. Landing.tsx and faq.ts say the opposite. Landing.tsx shows a fake CS-1042 log.

Work in this order. Do not start the next step until the current one has its “done when”.

1. One client-0 business across the three services.
   Code and docs only. List the env vars the owner must set herself, with no values: shared INTERNAL_TASK_SECRET, CRM_BASE_URL, EVOROVE_BASE_URL, EVOROVE_LEAD_BASE_URL, WEB_SEARCH_BASE_URL, AI_PROVIDER=anthropic plus the Anthropic key and model on the lead service, PUBLIC_API_BASE_URL, the mailbox connection, and payment.payment_link in Business DNA pointing at the Evorove subscription checkout.
   Done when: a short owner checklist exists in the repo, and the code refuses to send without a mailbox, a postal address, and PUBLIC_API_BASE_URL. You do not fill those values.

2. Search can run for real.
   In evorove_lead, keep the split: SearxNG fetches, Anthropic analyzes. Do not replace Anthropic with a literal copy of the page when the provider is anthropic. Do not pretend a search ran when WEB_SEARCH_BASE_URL is unset.
   Wire the CRM “find” call to that service. Same business id as cycle 2.
   Done when: a test shows a grounded person with an email becomes a Cold lead-touch, and a person with no reason is dropped. No message is sent from this repo.

3. One board.
   The dashboard at /app is the only CRM table. Cold people from cycle 1 show there. Clicking a row opens the dialogue on the right. Remove discard, pause, and takeover from that watch surface. Safety, STOP, and identity conflicts stay on /app/conversations.
   Done when: a Cold person with no conversation yet still appears on /app, the right pane says the engine has not written, and the watch UI has no closer buttons. Tests cover the tab mapping from lead-touch kinds, not only from ProcessState.

4. First email is built from the cycle-1 reading.
   Replace the generic template. The letter may use the grounded reason, the audience segment, and facts already in the refreshed materials or Business DNA. It may not invent a price, discount, guarantee, or a fact that has no source. The engine sends it. Do not add an approve screen.
   On send, report dialogue_started and the message body to CRM immediately enough that the tab becomes In progress and the right pane shows the text. Keep unsubscribe, quiet hours, suppression, and the daily cap.
   Done when: a test sends one email for a Cold person with a segment and a reason, asserts the body contains that reason, asserts no price, and asserts the CRM touch. A phone-only person is skipped, not texted.

5. The reply continues on the same card.
   An IMAP reply is the next turn. SalesPolicyEngine chooses the move. The configured production model phrases it. Do not switch on the companion.
   Done when: a test reply appears as the next line on that person’s card and does not open a second person.

6. Offer and Done for client 0.
   When the policy reaches the offer, the message uses the owner’s refreshed commercial offer and the DNA payment link. Done for this launch is the subscription payment recorded against that person. Do not mark Done only because a link string was concatenated, if the payment event has not happened. Do not collect the card. Calendar booking is out of this launch: client 0 is the subscription.
   Done when: a test payment event for that person moves the tab to Done, and a test with no payment event leaves them on Offer made.

7. Rehearsal on an address the owner controls.
   Do not run a live send yourself. Hand the owner the exact command and the inbox she must use. The fixture person in system/e2e.py does not count.
   Done when: she reports Cold → sent letter → reply → offer with her link → Done on the one dashboard. If she has not run it, say so. Do not write that client 0 is live.

8. The site stops contradicting the product.
   Fix the legal sentence that says finding people is not part of the service, so it matches the landing and the FAQ. Remove the fake CS-1042 sale log from the landing hero. Do not put a conversion percentage on the site.
   Done when: those strings are gone and the existing copy tests pass.

After step 7 only: daily search may stay scheduled. Do not send the first letter to a stranger inside this task.

Before editing, say which step you are on and which files you will touch.
After each step, say what is done and what the owner still has to type herself.
Run the focused tests for the behavior you changed. Do not run the whole suite unless a change crosses it.
Do not git push.
```
