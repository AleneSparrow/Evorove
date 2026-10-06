# Клиент 0: что задать самой

Один бизнес — Evorove, продажа своей подписки. Второй бизнес не заводить.
Один и тот же `business_id` в CRM, в цикле 2 и в `EVOROVE_CLIENT_ZERO_BUSINESS_ID`
на цикле 1. Локальный сид `acme-home-services` — фикстура `system/run-e2e.sh`,
не клиент 0.

Значений в этом файле нет. Их вводите вы. Агент их не читает и не подставляет.

Письмо не уходит, пока нет всех трёх: подключённый ящик, почтовый адрес в этом ящике,
`PUBLIC_API_BASE_URL` у продажи (на домене это api.evorove.com).

## Один секрет на три процесса

| Процесс | Переменная |
| --- | --- |
| продажа, журнал доски, поиск | `INTERNAL_TASK_SECRET` — одна и та же строка |

## Куда смотрят сервисы

Это URL внутри одного проекта Railway, не страницы, которые открывает владелец.

| Процесс | Переменная | Куда |
| --- | --- | --- |
| журнал доски | `EVOROVE_BASE_URL` | api.evorove.com |
| журнал доски | `EVOROVE_LEAD_BASE_URL` | внутренний адрес поиска |
| продажа | `CRM_BASE_URL` | внутренний адрес журнала доски |
| продажа | `PUBLIC_API_BASE_URL` | https://api.evorove.com |
| поиск | `CRM_BASE_URL` | тот же журнал доски |
| поиск | `EVOROVE_CLIENT_ZERO_BUSINESS_ID` | тот же `business_id`, что у продажи |
| поиск | `WEB_SEARCH_BASE_URL` | SearxNG. Пусто — поиск не запускался |
| поиск | `AI_PROVIDER` | `anthropic` |
| поиск | `ANTHROPIC_API_KEY` | ключ чтения страниц |
| поиск | `ANTHROPIC_MODEL` | модель чтения страниц |

В локальном `system/docker-compose.yml` поиск получает `AI_PROVIDER` из `LEAD_AI_PROVIDER`.
Так `AI_PROVIDER` продажи не переключается. Песочница не прод.

SearxNG только забирает страницы. Читает их Anthropic на поиске.
`AI_PROVIDER` продажи не переключать на companion LoRA.

## Ящик и оплата

Вводите на evorove.com, Settings.

- `ACCOUNT_SECURITY_ENCRYPTION_KEY` у продажи. Без него пароль ящика не сохраняется.
- Ящик: адрес отправителя, SMTP, IMAP, пароль и почтовый адрес (CAN-SPAM, не короче 10 символов).
  Пароль вводите вы. В ответ он не возвращается. API: `PUT /api/v1/businesses/{business_id}/integrations/email`.
- Payment link в Settings → Services & booking: checkout подписки Evorove.
  Это не цена в письме. Карту продукт не собирает.
  Ссылка в оффере оставляет карточку на Offer made. Done — только записанная
  оплата этого человека.

Движок отправляет сам. Отдельного экрана «одобрить каждое письмо» нет.
Первое письмо незнакомцу не отправлять, пока на `/app` не пройден ваш ящик:
Cold → письмо → ответ → оффер → Done.

## Репетиция на вашем ящике

Фикстура `system/run-e2e.sh` не считается. Живой поиск незнакомцев не запускать,
пока этот проход не виден на `/app`.

Ящик в Settings — тот, который вы читаете. Payment link — checkout подписки Evorove.

1. Положите **свой** адрес на Cold. Значения `BUSINESS_ID` и секрета вводите вы.
   `YOUR_INBOX` — почта, которую вы читаете. Это не незнакомец.

```bash
curl -sS -X POST "$CRM_BASE_URL/api/v1/internal/businesses/$BUSINESS_ID/lead-touches" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Task-Secret: $INTERNAL_TASK_SECRET" \
  -d '{
    "schema_version": "1",
    "touch_id": "rehearsal-assembled-1",
    "cycle": 1,
    "kind": "assembled",
    "source": "evorove_lead",
    "summary": "Owner rehearsal on an address she reads.",
    "identity": {"name": "Alena", "email": "YOUR_INBOX"},
    "payload": {
      "reason": "Owner rehearsal on an address she reads.",
      "reason_source": "owner rehearsal",
      "channel": "email",
      "segment": "owners watching one live board"
    }
  }'
```

2. Откройте `/app`. Карточка должна быть на Cold, справа — «The engine has not written»,
   затем письмо уходит само и вкладка становится In progress. Если письмо не ушло —
   нет ящика, почтового адреса или `PUBLIC_API_BASE_URL`.

3. Ответьте с того же ящика. Следующая строка должна появиться на той же карточке.

4. Когда в разговоре оффер — в письме ваша ссылка оплаты. Карточка остаётся на Offer made.

5. После реальной оплаты этого человека (не из-за самой ссылки) зафиксируйте Done:

```bash
curl -sS -X POST "$EVOROVE_BASE_URL/api/v1/internal/businesses/$BUSINESS_ID/people/$PERSON_ID/payment-recorded" \
  -H "X-Internal-Task-Secret: $INTERNAL_TASK_SECRET"
```

`PERSON_ID` возьмите из URL `/app?lead=...` или из ответа шага 1.

Только после этого: ежедневный поиск и кнопка Find people на Cold. Не слать первое
письмо незнакомцу из этой репетиции.

Поиск вручную, когда будете готовы (не репетиция):

```bash
python -m evorove_lead.client_zero
```

Печатает только счётчики. `messages_sent` всегда 0. Без `WEB_SEARCH_BASE_URL` выходит с кодом 2.
