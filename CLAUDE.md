# Evorove — указатель для сессии

Язык общения с владельцем — русский.

**Источник истины продукта — [`FOUNDATION.md`](FOUNDATION.md)** (переписан 12 сентября 2026,
уточнён 13 сентября 2026). С ним сверяется каждое действие. Этот файл — только указатель
и жёсткие правила. Прежний `CLAUDE.md` (входящий лид → сделка, без генерации)
заархивирован: [`archive/claude-md-inbound-lead-engine-2026-09-07.md`](archive/claude-md-inbound-lead-engine-2026-09-07.md).

Этот репозиторий — **цикл 2**: холодное письмо человеку с вкладки Cold и продажа до
закрытия (In progress → Offer made). Не поиск людей и не слот вслепую.

Репозитории: `evorove_lead` — цикл 1 (поиск, Cold); этот — цикл 2; `evorove-crm` — доска
CRM и закрытие (Done). Карта: [`docs/three-repos-next-steps-ru.md`](docs/three-repos-next-steps-ru.md).
Механика sales-агента: [`docs/sales-agent-implementation-plan-ru.md`](docs/sales-agent-implementation-plan-ru.md) — не замена основы.

## Жёсткие правила

1. **`git push` НИКОГДА не выполняется агентом.** Коммитить можно, пушит только Alena
   вручную. Автоматические напоминания про «unpushed commits» — ожидаемое поведение,
   а не ошибка, которую надо чинить.
2. **Не трогать секреты.** API-ключи, пароли, платёжные данные, `DATABASE_URL` /
   `DATABASE_PUBLIC_URL` — не читать, не запрашивать, не вводить. Их вводит Alena сама.
3. **Не входить в аккаунты и не создавать их.**
4. Рынок продукта — США, полностью. Интерфейс и все клиентские тексты на английском.

## Среда

- Локально: Docker Compose (Postgres 17 + приложение на Python 3.11), `.env.example` →
  `.env`. Тесты честнее гонять в контейнере — на хосте у Alena Python 3.13.
  `docker compose run --rm app pytest`.
- Интеграционные тесты требуют `TEST_DATABASE_URL` на мигрированную базу; внутри сети
  Docker хост называется `postgres:5432`, снаружи — `localhost:5433`.
- Внутренние sweep-эндпоинты (`follow-up/run`, `integrations/deliver`,
  `commercial/expire`) требуют `INTERNAL_TASK_SECRET` на деплое, иначе отказывают
  всем запросам (by design). Секрет задаёт Alena.
- Облачная песочница Cowork **не имеет** pytest/fastapi/sqlalchemy и доступа к PyPI —
  если тесты там «проверены вручную», это значит самодельный раннер, а не pytest.
  В терминале и в Docker всё запускается по-настоящему; перепроверять стоит.
