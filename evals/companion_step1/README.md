# Companion Step 1 — dataset folder

**Cycle 2 mouth only.** Not people search. Not booking. Not an approved playbook.  
**Ready for Step 2 training:** see `docs/sales-knowledge/corpus-registry.json` (`sft_core_titles`). Training job is never started by ingest. Archive-mapped and unmapped files do not unlock SFT.

Step 2 local LoRA export: `evals/companion_step2/`. Dry-run: `python3 scripts/train_companion_lora.py`. Do not train on the alpaca/chatml/sharegpt pack below.

Use these files for the companion contract:

| File | Role |
| --- | --- |
| `docs/sales-knowledge/corpus-manifest-step1.md` | Licence catalog |
| `docs/sales-knowledge/companion-dataset-spec.md` | JSONL shape |
| `data/analyzer.jsonl` | `SalesTurnAnalysisOutput` rows |
| `data/generator.jsonl` | `SalesResponseOutput` rows |
| `fixtures.json` | Eval cases including negatives |
| `data/derived/*.jsonl` | Extra analyzer/generator rows unlocked after a deposited **core** title |
| `docs/sales-knowledge/how-to-deposit-books-ru.md` | Owner: drop books, run ingest |

Do **not** fine-tune on `data/alpaca_*.jsonl`, `chatml_*.jsonl`, or `sharegpt_*.jsonl`. That pack is owner-deposited textbook Q&A. It treats Feel-Felt-Found as a correct answer, which spec 0.4 forbids as a positive example.

The zip and `knowledge_base.xlsx` stay here as an index. Cards stay unapproved.

---

# Sales Training LLM — папка проекта


Распаковано в `evals/companion_step1/` (Evorove, шаг 1 companion-модели).
Архив лежит здесь же и в `private/sales-corpus/` (локальная копия, в git не
попадает). Карточки и веса из этого пакета не утверждены. Feel-Felt-Found в
датасете есть как учебный ответ — в позе продукта 0.4 это **не** положительный
пример обучения агента.

Датасет и материалы для дообучения (fine-tuning) или RAG-подключения LLM
по теме «обучение продажам» (21 тема: психология продаж, SPIN/Challenger/
MEDDIC, работа с возражениями, переговоры, CRM, аналитика продаж и т.д.).

## Структура папки

```
project/
├── README.md                      ← этот файл
├── data/                          ← готовые датасеты для обучения
│   ├── alpaca_train.jsonl         (145 примеров) — формат Alpaca {instruction, input, output}
│   ├── alpaca_val.jsonl           (16 примеров)  — валидационная выборка
│   ├── chatml_train.jsonl         (145 примеров) — формат OpenAI/ChatML {messages:[...]}
│   ├── chatml_val.jsonl           (16 примеров)
│   ├── sharegpt_train.jsonl       (145 примеров) — формат ShareGPT {conversations:[...]}
│   ├── sharegpt_val.jsonl         (16 примеров)
│   └── raw_with_topics.jsonl      (161 пример)   — исходные пары + поле "topic" для фильтрации/анализа
├── sources/
│   └── sources.csv                — 84 ссылки на первоисточники (для ручного сбора доп. данных)
└── docs/
    └── knowledge_base.xlsx        — полная база знаний (9 листов: темы, книги, фреймворки,
                                      кейсы, метрики, инструменты, источники, оговорки)
```

## Какой формат выбрать под ваш фреймворк

| Формат | Файлы | Подходит для |
|---|---|---|
| **Alpaca** | `alpaca_train.jsonl` / `alpaca_val.jsonl` | LLaMA-Factory, Axolotl, Unsloth, большинство open-source SFT-скриптов (`instruction/input/output`) |
| **ChatML / OpenAI messages** | `chatml_train.jsonl` / `chatml_val.jsonl` | OpenAI Fine-tuning API, Anthropic/Claude fine-tuning (где поддерживается), vLLM chat-шаблоны, most instruct-модели с системным промптом |
| **ShareGPT** | `sharegpt_train.jsonl` / `sharegpt_val.jsonl` | Axolotl, FastChat, LLaMA-Factory (`conversations` с ролями human/gpt) |
| **Raw + topic** | `raw_with_topics.jsonl` | Не для прямого обучения — удобно для фильтрации по теме, ручной доработки, генерации доп. примеров, или как источник для RAG-индекса |

Все три обучающих формата содержат **одни и те же 161 пару** вопрос-ответ,
просто упакованные под разные загрузчики данных — выбирайте один, не все три.

## Быстрый старт (пример — LLaMA-Factory / Alpaca)

```bash
# пример конфигурации dataset_info.json для LLaMA-Factory
{
  "sales_training": {
    "file_name": "alpaca_train.jsonl",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

## Пример конфигурации (ChatML / OpenAI fine-tuning)

Файл `chatml_train.jsonl` уже в формате, который принимает OpenAI Fine-tuning API
(`messages: [system, user, assistant]`) — загружайте как есть через
`openai api fine_tunes.create` или аналогичный вызов для вашей платформы.

## Важные ограничения — прочитайте перед обучением

1. **Объём датасета мал для полноценного файнтюнинга.** 161 пример (145 в train)
   достаточно для:
   - LoRA/QLoRA дообучения «стиля и терминологии» на базовой instruct-модели;
   - seed-датасета, который стоит расширить синтетической аугментацией
     (см. ниже) или ручными примерами из реальных диалогов/скриптов продаж;
   - **не** для обучения модели «с нуля» знаниям — для этого лучше подойдёт RAG
     (поиск по `docs/knowledge_base.xlsx` в момент ответа), а не веса модели.

2. **Тексты в датасете — авторские формулировки, не копии источников.**
   Ответы синтезированы на основе фактов и концепций (авторы, годы, статистика,
   суть фреймворков), а не являются дословными выдержками из книг или статей.
   Это сделано осознанно, чтобы не нарушать авторские права правообладателей
   (Cialdini, Rackham, Voss, Gartner, Gong и др.). Если нужен больший объём —
   легально приобретите материалы по ссылкам из `sources/sources.csv` и
   создайте на их основе собственные QA-пары в соответствии с лицензией
   каждого источника.

3. **Как расширить датасет:**
   - разбейте существующие развёрнутые ответы на более мелкие Q&A;
   - сгенерируйте перефразированные версии вопросов (paraphrasing) для тех же
     ответов — это валидная техника аугментации, не путать с копированием
     чужого контента;
   - добавьте ролевые диалоги («клиент возражает — продавец отвечает») на
     основе фреймворков из `docs/knowledge_base.xlsx` (лист «Фреймворки и методы»).

## Источники (`sources/sources.csv`)

Колонки: `Название материала, Издатель/автор, Ссылка, Тема`.
Используйте этот файл, чтобы вручную перейти по ссылкам и (там, где
разрешено лицензией) собрать дополнительные обучающие примеры или
подключить материалы как внешнюю базу для RAG.
