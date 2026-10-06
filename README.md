# Evorove

Основа продукта — [`FOUNDATION.md`](FOUNDATION.md).
Как делали по этапам — [`docs/project-path-ru.md`](docs/project-path-ru.md).
Документы этапов — [`archive/`](archive/), не удалены.

Сайт и кабинет: [evorove.com](https://evorove.com). API: [api.evorove.com](https://api.evorove.com).

Этот репозиторий — цикл 2: письмо с Cold и продажа. Поиск — `evorove_lead`.
Журнал вкладок — `evorove-crm`. Один проект Railway.

Правила сессии: [`CLAUDE.md`](CLAUDE.md), [`AGENTS.md`](AGENTS.md).
Деплой: [`DEPLOY.md`](DEPLOY.md).

## Тесты

На хосте Python 3.13. Честнее в контейнере (3.11):

```bash
docker compose run --rm app pytest
```

## Локально

```bash
cp .env.example .env
docker compose up -d postgres
docker compose up --build
```

Сид `acme-home-services` — фикстура, не клиент 0. Клиент 0 — Evorove на evorove.com.
