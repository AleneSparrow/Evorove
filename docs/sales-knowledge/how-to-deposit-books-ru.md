# Как положить книги для companion-модели

Цикл 2: модель рядом с агентом формулирует уже выбранный `SalesMove`. Это не поиск людей и не бронь. Карточки не утверждаются. Training job скрипт **не** запускает.

Каталог **не закрыт.** Пока шаг 2 не начат, новые купленные файлы можно класть в любой момент. Не нужно «дожать все книги» одним проходом.

## Что сделать вам

1. Купите или лицензируйте книги сами. Агент их не скачивает (ни LibGen, ни торренты).
2. Положите файлы сюда: `private/sales-corpus/incoming/`
   - форматы: PDF, EPUB, FB2, TXT, MD, HTML, DOCX (иногда EPUB внутри 7z)
   - имя файла лучше узнаваемое: `SPIN_Selling.pdf`, `Never_Split_the_Difference.epub`, `Influence_Cialdini.pdf`
3. Положить файл = ваша отметка «это моя легальная копия». Рядом скрипт сам создаст `Имя.pdf.licence.json`. При желании поправьте поля `licence` (`purchase` / `publisher-licence` / `my-copy`) и автора.
4. Из корня репозитория:

```bash
python scripts/ingest_sales_corpus.py
python scripts/ingest_sales_corpus.py --status
```

`ready_for_step2_training: true` значит: есть хотя бы одна книга **ядра**. Это **не** стоп для новых книг и **не** старт обучения. Обучение весов — `python3 scripts/train_companion_lora.py --run` (локальная LoRA), отдельное решение.

## Ядро и архив

SFT-строки пишутся **только из ядра** (живой ход цикла 2): SPIN, Challenger, Influence, Voss, Blount, Sandler, Getting to Yes, Konrath, StoryBrand, Рысев, HBR Sales, Броди, Заид, Hsieh.

Остальное — **архив**: файл регистрируется, текст извлекается локально, пары в `derived/` не появляются. Сюда же попадают unmapped-имена, ритейл, карьера, саммари Smart Reading, skip-полярность.

Чтобы перевести книгу из архива в ядро — needles уже есть, плюс явный `catalog_id` в `CORE_CATALOG_IDS`. Incoming по-прежнему открыт.

## Как добавлять ещё

- Ещё один файл в `incoming/` → снова ingest. Старые депозиты не стираются.
- Незнакомое имя попадёт в `unmapped_files`: файл зарегистрирован, текст извлечён локально, положительные SFT-строки сами не появятся.
- Чтобы книга узнавалась: узнаваемое имя **или** needles в `src/companion_corpus/known_titles.py`.
- Короткие правила (не главы) — по желанию в `src/companion_corpus/rulebook.py` под тем же `catalog_id`. Без правил книга всё равно лежит в реестре.

## Что делает скрипт

- регистрирует файлы в `docs/sales-knowledge/corpus-registry.json` (имена, хеш, страницы — не текст книги);
- кладёт извлечённый текст только в `private/sales-corpus/.extracted/` (git это игнорирует);
- пишет производные пары в `evals/companion_step1/data/derived/` под схемы анализатора и генератора;
- оставляет карточки `candidate`, version 0.

Известные названия растут в `known_titles.py` (SPIN, Challenger, Influence, Voss, Blount, Sandler, Getting to Yes, Konrath, StoryBrand, Grant, Ferrazzi, Seligman, Tracy, Cuddy, Navarro, Thaler, Ariely, Kahneman и другие по мере добавления). Список не конечный.

Пакет `evals/companion_step1/data/alpaca_*.jsonl` в обучение агента **не** идёт: там Feel-Felt-Found как правильный ответ, поза 0.4 это запрещает.

## Не делать

- просить агента скачать закрытые PDF;
- коммитить книги;
- утверждать карточки из ingest;
- кормить companion датасетом alpaca/chatml/sharegpt из owner-zip;
- считать текущий набор книг финальным каталогом.
