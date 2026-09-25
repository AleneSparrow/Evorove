# Prompt: цикл 2 — движок + рот к проду (12 сентября 2026)

Владелец зафиксировал продуктовую картину. Этот файл — карта **цикла 2** и промпт. Цикл 1 и слот в CRM не делать здесь.

Скопируйте блок в конце агенту из корня `/Users/alenakulish/dev/evorove`.

---

## Картина (владелец, 12 сентября)

- Три цикла — одна система. Цикл 1 **ищет и квалифицирует** (человек + причина + предпочтительный канал). Письма от цикла 1 нет.
- Карточка **Found** пишется в CRM-журнал (4 этапа: Found → Opened → In play → Hot). Это память движка, не рассылка из CRM.
- Цикл 2 **читает карточку и сам пишет**. Владелец бизнеса **не вмешивается** в переписку (портит продажу и статистику). Смотрит дашборд. Человек — только STOP / emergency / policy; такие кейсы **не** в знаменателе конверсии. `REQUEST_BUSINESS_FACT` — факт владельцу, не захват чата.
- Аккаунты соцсетей бизнеса **не берём**. Соцсети — сбор в цикле 1. Пишем с **каналов Evorove** с припиской, какой это бизнес.
- Мессенджеры (WhatsApp и др.) — рот разговора, когда канал и согласие есть. SMS/email — запасные рты (SMS исходящий уже есть; sales-email ещё нет).
- Библиотека материалов бизнеса — факты для `PRESENT_RELEVANT_VALUE`, не генерация картинок из воздуха.
- УТП владельца: рабочая **подтверждённая** конверсия после пилота. На лендинг **число не писать**, пока нет знаменателя. `FOUNDATION.md` / `AGENTS.md` ещё говорят агентам не обещать процент — не ставить % в копирайт; измерять воронку можно.
- Рот: `SalesPolicyEngine` выбирает `SalesMove`. LLM (сейчас production provider; LoRA 3B/7B обучены, **не** в `AI_PROVIDER`) формулирует. `mouth_guard` обязателен перед JSON адаптера. GPU/Together — не этот срез.

---

## Что в цикле 2 уже есть

- `FoundPerson` + ingest `POST /api/v1/internal/businesses/{id}/found` (секрет внутренних задач). Send: `sms` | `email`. `preferred_channel` / `messenger_id` на карточке; WhatsApp send не включён. POST в CRM с ingest нет.
- `phrase_outbound_greet` — **Evorove for {business}**, без «you reached out».
- Владелец не в обычном чате. Библиотека материалов: Refresh → презентация берёт **один** факт.
- Виджет — входящий канал. Twilio SMS — исходящий/входящий тред.
- Live turn, политика, валидатор, `hot_lead_handoff` payload; POST в CRM при `CRM_BASE_URL`.
- Companion LoRA + локальный endpoint + `mouth_guard`. Прод-рот не переключён.

---

## Полные шаги цикла 2 до прода (порядок)

Не начинать следующий, пока у текущего нет «готово, когда».

| # | Шаг | Готово, когда | Где |
| --- | --- | --- | --- |
| C2-0 | Приём Found из CRM-журнала | **Готово 12 сентября 2026 (API).** Контракт + `POST /api/v1/internal/businesses/{id}/found`. Без причины — отказ. Цикл 2 не ищет людей. Живой POST из CRM — у агента CRM по контракту | `found_person.py`, internal ingest |
| C2-1 | Подпись Evorove | **Готово 12 сентября 2026.** Первый ход: English, лид видит Evorove **for** {business}. Не «тайный салон». Не аккаунт салона | `phrase_outbound_greet`, промпты, тесты |
| C2-2 | Владелец не в чате | **Готово 12 сентября 2026.** Нет UI «ответить как сотрудник» на обычной продаже. Дашборд read-only. Reply только после риска. HUMAN_REVIEW вне знаменателя конверсии. STOP не ослаблен | Conversations / stats; `StaffActionService` |
| C2-3 | Библиотека материалов | **Готово 12 сентября 2026.** Владелец грузит фото/видео/PDF/прайс как факты. Презентация берёт одно релевантное из Refresh. Нет выдуманного креатива | Settings → Materials; `owner_material_pick` |
| C2-4 | Каналы рта | **Готово 12 сентября 2026.** WhatsApp через провайдер Evorove (`whatsapp_opt_in`, `EVOROVE_WHATSAPP_FROM`). SMS уже. Email продажи — позже. Соцсеть не Direct | `whatsapp_mouth.py`; `ALLOWED_OUTBOUND_CHANNELS` |
| C2-5 | Тред до горячего | **Готово 12 сентября 2026.** Ответ лида на GREET — тот же `SalesLiveTurn`. Журнал: `opened` / `in_play` / `hot` через outbox `lead-touches`. POST hot_lead нет | live turn + `crm_touch` outbox |
| C2-6 | Выход Hot | **Готово 12 сентября 2026.** `OFFER_BOOKING_SLOTS` → outbox POST `/hot-leads`. Слота в payload нет. Бронь в `evorove` не удалена | `hot_lead_handoff.py` + `crm_hot_lead` outbox |
| C2-7 | Рот LLM | Eval сида (`eval_companion_lora.py`) когда владелец примет зависший Mac **или** eval через уже поднятый `:8741`. `mouth_guard` на каждой генерации. `AI_PROVIDER` менять **только** после eval и явной фразы владельца. До этого прод = Claude/настроенный LLM | `mouth_guard`, generator/analyzer wrap; не Together 24/7 |
| C2-8 | Воронка и тесты | События: Found / first sent / in play / hot / STOP / human. Pytest на согласие, подпись, материалы, запрет ручного дожима. Живой прогон на синтетическом номере — владелец | tests + analytics events |
| C2-9 | Не этот репо | Поиск людей, Ads OAuth, слот, вечерний экран записей | `evorove_lead` / `evorove-crm` |

---

## Текущий срез для агента ниже

C2-0…C2-6 закрыты 12 сентября 2026. Следующий агент: **C2-7** (рот LLM / eval companion). Не менять `AI_PROVIDER` без eval и явной фразы владельца.

---

```text
Read these files first, in this order, and follow them:
1. FOUNDATION.md
2. docs/foundation-alignment-stage-ru.md
3. AGENTS.md
4. CLAUDE.md
5. docs/agent-prompts/cycle-2-engine-prod-next-agent.md
6. docs/sales-agent-implementation-plan-ru.md (banner, 0.1, 0.3, 1–2, 4–5, 11)
7. src/domain/found_person.py
8. src/persistence/outbound_first_touch.py
9. src/engine/sales_live_turn.py (phrase_outbound_greet)
10. src/domain/hot_lead_handoff.py
11. src/companion_corpus/mouth_guard.py

Talk to the owner in Russian. Product UI and customer-facing copy stay English. US market.
This repo is cycle 2 only (sale until ready to book). Cycle 1 is evorove_lead. Cycle 3 is evorove-crm.

Owner picture (12 Sep 2026) — obey it:
- Cycle 1 finds + qualifies (person + reason + preferred channel). It does not message.
- Found card is stored in the CRM journal (4 stages Found → Opened → In play → Hot). CRM does not send.
- Cycle 2 reads the card and writes. Tenant owner watches only; no manual takeover of a normal sale (spoils stats). Human = STOP / emergency / policy only; those rows out of conversion denominator. REQUEST_BUSINESS_FACT stays.
- Do not ask for the tenant’s social logins. Social = cycle 1 collection. Mouth = Evorove-branded channel with “Evorove for {business}”.
- Materials library is closed (C2-3). Presentation picks one activated fact. Cycle 1 still reads the website.
- Do not put a conversion percentage on the landing page. Measuring funnel events is allowed. Do not rewrite FOUNDATION.md unless the owner asks to change the conversion-copy rule this turn.
- SalesPolicyEngine chooses SalesMove. Do not change AI_PROVIDER. Do not start Together/GPU. Do not train LoRA unless they say scripts/train_companion_lora.py --run.

This turn — only:
1. Mouth channels: WhatsApp/messenger via **Evorove’s** provider, not the tenant’s OAuth page. SMS already exists. Do not treat social Direct as the mouth.
2. Keep GREET, owner-out-of-chat, and materials as they are. Do not POST hot_lead to CRM unless the owner names C2-6.

Do not
- git push. Read or edit .env / secrets. Create accounts.
- Search people. Scrape. Approve knowledge cards. Feed alpaca/chatml/sharegpt.
- Merge SalesStage into ProcessState. Book a slot. Build a blast UI.
- Wire the LoRA into live turns. Promise a conversion rate on customer UI.

Verify
- .venv/bin/python -m pytest tests/test_marketing_materials.py tests/test_sales_live_turn.py tests/test_outbound_first_touch.py tests/test_staff_sale_takeover.py -q
  (adjust to the test files you actually touch; do not weaken tests)

Handoff
- What changed, tests pass/fail, what C2 step is next (C2-7 LLM mouth eval).
```
