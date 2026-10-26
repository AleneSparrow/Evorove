# Контракт: Found из CRM-журнала → цикл 2

Цикл 2 **не ищет людей**. CRM держит карточку Found (память журнала Found → Opened → In play → Hot). Этот репозиторий **читает карточку и пишет** GREET. CRM **не** шлёт письмо. Слот не ставится.

Эмит касаний в журнал (C2-5): `opened` после GREET, `in_play` на ответ лида, `hot` когда готов к записи. Это события в `POST .../lead-touches` (outbox). Когда человек готов к записи, цикл 2 также POST `hot-leads` в CRM (C2-6). Слот в payload нет. WhatsApp send — номер Evorove.

## Приём

```
POST /api/v1/internal/businesses/{business_id}/found
Header: X-Internal-Task-Secret: <INTERNAL_TASK_SECRET>
Content-Type: application/json
```

Тот же секрет, что у внутренних sweep. Без секрета эндпоинт выключен (401). Владелец бизнеса этот URL не вызывает с дашборда.

## Тело

| Поле | Обязательно | Смысл |
| --- | --- | --- |
| `schema_version` | нет, по умолчанию `1` | Версия карточки |
| `person_id` | да | Стабильный id человека в журнале CRM |
| `reason` | да | Заземлённая причина (не дамп контакта). Короткий «Ada +1…» — отказ |
| `source` | да | Откуда факт (цикл 1), не «мы нашли в CRM» |
| `preferred_channel` | нет | `sms` \| `email` \| `whatsapp` — предпочтение на карточке |
| `channel` | нет, если `preferred_channel` уже send-рот | Рот **отправки**: `sms` \| `email` \| `whatsapp` |
| `consent_basis` | да для отправки | SMS: `prior_express_written`. Email: `email_opt_in`. WhatsApp: `whatsapp_opt_in`. Inferred / widget / public_post — отказ |
| `identity.name` | нет | |
| `identity.phone` | да, если рот `sms` или `whatsapp` (или `wa:` / `whatsapp:` messenger id) | |
| `identity.email` | да, если рот `email` | |
| `identity.gender` | нет | Только если цикл 1 **уже записал**. Не угадывать по имени |
| `identity.region` | нет | Только если цикл 1 **уже записал** (штат / город). Не выводить из ZIP здесь |
| `idempotency_key` | нет | По умолчанию `found:{person_id}` |
| `observed_pain` | нет, но нужен для касания на боли | Конкретная проблема человека, найденная циклом 1 (до 500 символов). Первое сообщение открывается ею. Ярлык вместо описания — отказ. См. [`pain-first-touch-ru.md`](pain-first-touch-ru.md) |

`preferred_channel=whatsapp` **без** `channel=sms` или `email` пишет в WhatsApp при `whatsapp_opt_in`. SMS-согласие `prior_express_written` **не** открывает WhatsApp. `channel=sms` при предпочтении WhatsApp по-прежнему шлёт SMS.

Соцсети бизнеса (IG Direct и т.п.) — не рот. Не присылать `instagram`. Email send по-прежнему позже.

## Ответ 200

Тот же смысл, что исходящий GREET: `case_id`, `conversation_id`, `lead_id`, `move=GREET_AND_SET_CONTEXT`, `message_text` (Evorove for {business}), `delivered`, `duplicate`.

Повтор той же карточки — `duplicate: true`, второе SMS не уходит.

## Ошибки

- `401` — нет / неверный секрет
- `404` `business_not_found`
- `422` с `error.code`: `found_person_reason_required`, `found_person_id_required`, `observed_pain_not_grounded`, `outbound_consent_required`, `whatsapp_not_configured`, `outbound_channel_invalid`, …
- `409` `sms_suppressed` / `conversation_already_active`

Цикл 2 **не** шлёт POST `hot_lead` из ingest. GREET кладёт событие `opened` в журнал. Горячий выход — отдельный `POST .../hot-leads` после `OFFER_BOOKING_SLOTS`.

## Холодное письмо из CRM (`lead-commands`)

Основной маршрут первого касания из CRM — не этот эндпоинт, а `POST /api/v1/internal/businesses/{business_id}/lead-commands` с `action=cold_assigned`. Там `payload.observed_pain` (необязательно, до 500 символов) открывает письмо. Одному человеку — один маршрут. См. [`pain-first-touch-ru.md`](pain-first-touch-ru.md).
