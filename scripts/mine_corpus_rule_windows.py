#!/usr/bin/env python3
"""Mine short keyword windows from owner-extracted copies.

Output stays under private/sales-corpus/.extracted/ (gitignored).
Never print or copy chapter text into git.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "evals" / "companion_step1" / "derived" / "deposit-index.json"
EXTRACTED = ROOT / "private" / "sales-corpus" / ".extracted"
OUT = EXTRACTED / "rule-windows.json"

KEYWORDS: dict[str, tuple[str, ...]] = {
    "spin-selling": (
        "ситуационн",
        "проблемн",
        "извлекающ",
        "направляющ",
        "need-payoff",
        "implication",
        "закрыти",
        "потребност",
        "spin",
    ),
    "challenger-sale": (
        "челленджер",
        "чемпион",
        "инсайт",
        "reframe",
        "teaching",
        "конструктивн",
        "отношен",
        "challenger",
    ),
    "influence": (
        "взаимность",
        "reciprocity",
        "обязательств",
        "consistency",
        "социальное доказательство",
        "дефицит",
        "scarcity",
        "авторитет",
        "симпат",
        "единство",
    ),
    "never-split-the-difference": (
        "калибр",
        "лейбл",
        "label",
        "зеркал",
        "that's right",
        "это правильно",
        "компромисс",
        "нет",
        "тактическ",
    ),
    "fanatical-prospecting": (
        "проспект",
        "касани",
        "воронк",
        "отказ",
        "телефон",
        "follow",
        "multi",
        "квота",
    ),
    "sandler-rules": (
        "закон",
        "квалиф",
        "боль",
        "деньг",
        "решени",
        "iou",
        "конфет",
        "sandler",
        "сделка",
    ),
    "getting-to-yes": (
        "интерес",
        "позици",
        "batna",
        "альтернатив",
        "объективн",
        "принцип",
        "опцион",
        "люд",
    ),
    "selling-to-big-companies": (
        "ассистент",
        "триггер",
        "доступ",
        "лицо",
        "ценност",
        "голос",
        "email",
        "решени",
    ),
    "agile-selling": (
        "обучен",
        "привычк",
        "нович",
        "скорост",
        "crm",
        "навык",
        "практик",
    ),
    "storybrand": (
        "герой",
        "проводник",
        "злодей",
        "план",
        "призыв",
        "провал",
        "успех",
        "история",
    ),
    "storybrand-2": (
        "герой",
        "проводник",
        "план",
        "призыв",
        "трансформац",
        "ясность",
    ),
    "storybrand-funnel": (
        "воронк",
        "письмо",
        "призыв",
        "лид",
        "сайт",
        "одношаг",
        "nurture",
    ),
    "give-and-take": (
        "отдавать",
        "брать",
        "matcher",
        "giver",
        "taker",
        "взаимн",
        "сеть",
    ),
    "never-eat-alone": (
        "сеть",
        "отношен",
        "щедрость",
        "завтрак",
        "контакт",
        "follow",
    ),
    "learned-optimism": (
        "оптимизм",
        "объяснительн",
        "выученн",
        "беспомощн",
        "стиль",
    ),
    "eat-that-frog": (
        "лягушк",
        "приоритет",
        "прокрастин",
        "план",
        "самое важное",
    ),
    "presence": (
        "присутствие",
        "сила",
        "уверенность",
        "поза",
        "голос",
    ),
    "what-every-body-is-saying": (
        "жест",
        "лицо",
        "лож",
        "кластер",
        "базов",
        "ноги",
    ),
    "nudge": (
        "подталкиван",
        "выбор",
        "default",
        "архитектур",
        "либерт",
    ),
    "predictably-irrational": (
        "якорь",
        "бесплатн",
        "иррационал",
        "сравнен",
        "социальн",
    ),
    "thinking-fast-slow": (
        "система 1",
        "система 2",
        "system 1",
        "эвристик",
        "якорь",
        "доступност",
        "неприяти",
    ),
}

MAX_HITS_PER_KEY = 4
WINDOW_WORDS = 18


FILENAME_BUCKETS: tuple[tuple[str, str], ...] = (
    ("спин-продажи", "spin-selling"),
    ("чемпионы продаж", "challenger-sale"),
    ("чалдини", "influence"),
    ("influence", "influence"),
    ("восс", "never-split-the-difference"),
    ("блаунт", "fanatical-prospecting"),
    ("49 законов", "sandler-rules"),
    ("переговоры без поражения", "getting-to-yes"),
    ("большим компаниям", "selling-to-big-companies"),
    ("гибкие продажи", "agile-selling"),
    ("storybrand 2", "storybrand-2"),
    ("storybrand_2", "storybrand-2"),
    ("воронки продаж", "storybrand-funnel"),
    ("метод storybrand", "storybrand"),
    ("брать или отдавать", "give-and-take"),
    ("ешьте в одиночку", "never-eat-alone"),
    ("селегман", "learned-optimism"),
    ("оптимизму", "learned-optimism"),
    ("лягушку", "eat-that-frog"),
    ("кадди", "presence"),
    ("наварро", "what-every-body-is-saying"),
    ("nudge", "nudge"),
    ("ариели", "predictably-irrational"),
    ("канеман", "thinking-fast-slow"),
    ("thinking, fast", "thinking-fast-slow"),
)


def bucket_for(deposit: dict) -> str | None:
    catalog = deposit.get("catalog_id")
    if catalog:
        return catalog
    hay = deposit["filename"].replace("_", " ").replace("-", " ").casefold()
    hits = [bucket for needle, bucket in FILENAME_BUCKETS if needle in hay]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        return max(hits, key=len)
    return None


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _window(words: list[str], index: int) -> str:
    start = max(0, index - 4)
    end = min(len(words), index + WINDOW_WORDS)
    return " ".join(words[start:end])


def mine_pages(pages: list[str], keys: tuple[str, ...]) -> list[dict]:
    hits: list[dict] = []
    counts: dict[str, int] = {}
    for page_no, page in enumerate(pages, start=1):
        lowered = page.casefold()
        words = _words(page)
        lowered_words = [w.casefold() for w in words]
        blob = " ".join(lowered_words)
        for key in keys:
            if counts.get(key, 0) >= MAX_HITS_PER_KEY:
                continue
            if key.casefold() not in blob:
                continue
            # Find a word index near the key.
            idx = blob.find(key.casefold())
            prefix = blob[:idx]
            word_index = prefix.count(" ")
            counts[key] = counts.get(key, 0) + 1
            hits.append(
                {
                    "key": key,
                    "chunk": page_no,
                    "window": _window(words, word_index),
                }
            )
    return hits


def main() -> int:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    reports: list[dict] = []
    for deposit in index["deposits"]:
        catalog = bucket_for(deposit)
        sha = deposit["sha256"]
        path = EXTRACTED / f"{sha}.txt"
        if not path.exists():
            reports.append({"filename": deposit["filename"], "error": "missing extract"})
            continue
        pages = [p.strip() for p in path.read_text(encoding="utf-8").split("\n\n\f\n\n") if p.strip()]
        keys = KEYWORDS.get(catalog or "")
        if keys is None:
            # Unmapped books: try filename-based bucket later; skip keys.
            reports.append(
                {
                    "filename": deposit["filename"],
                    "catalog_id": catalog,
                    "page_count": len(pages),
                    "hits": [],
                    "note": "no keyword list for catalog yet",
                }
            )
            continue
        reports.append(
            {
                "filename": deposit["filename"],
                "catalog_id": catalog,
                "page_count": len(pages),
                "hits": mine_pages(pages, keys),
            }
        )
    OUT.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "books": len(reports)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
