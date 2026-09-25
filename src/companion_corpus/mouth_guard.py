"""Deterministic companion mouth guard. AI JSON is untrusted.

Does not change AI_PROVIDER. Does not load mlx. Does not freeze the machine.
"""

from __future__ import annotations

import re
from copy import deepcopy
from functools import lru_cache
from typing import Any

END_CONTACT_CLOSE = (
    "You have been unsubscribed and won't hear from us again about this."
)
SAFE_NO_GIFT = (
    "I can't invent an add-on that is not in our facts. "
    "Want the consult hour while the missed follow-up is still loud, or sit with it?"
)
FFF = ("i understand how you feel", "others have felt", "what they found")
OBJECTION_ALIASES = {"TIME": "TIMING"}
DEFAULT_GIFT_PATTERNS = (r"free extra", r"throw in", r"on the house")
SAFE_NO_FFF = (
    "That landed. What's loudest right now — the wait, the money, or whether this even fits?"
)
SAFE_NO_QUOTE = (
    "Let me put that in my own words instead of quoting it back to you."
)
# Step 3 coverage pass 2.5 (12 September 2026): the owner asked for the
# companion to draw on full book text without ever quoting it to a
# customer. A run of this many consecutive words matching any depositied
# core-catalog chunk verbatim is treated as a quote, not a paraphrase,
# regardless of whether the text reached the model through a training
# row, a RAG-retrieved chunk (`rag.py`), or anything else -- the guard
# does not care how the words got into the output.
QUOTE_MIN_WORDS = 8
_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ]+")


def high_risk_analyzer(row: dict[str, Any]) -> bool:
    if str(row.get("id", "")).startswith(("an-stop", "an-injection", "an-emergency")):
        return True
    message = str(row.get("customer_message") or "").casefold()
    if re.search(r"^\s*stop\b", message) or "do not text me" in message:
        return True
    if "ignore previous" in message or "system prompt" in message or "developer prompt" in message:
        return True
    if "disregard your rules" in message or "you are now dan" in message:
        return True
    return "emergency" in message and ("arrest" in message or "lawyer tonight" in message)


@lru_cache(maxsize=1)
def _corpus_word_sequences() -> tuple[str, ...]:
    """Every depositied core-catalog chunk, word-tokenized the same way
    as `_quote_windows` and rejoined with single spaces.

    Original punctuation and whitespace in the extracted text (line
    breaks, multi-space runs, attached punctuation) would otherwise make
    a real verbatim quote fail a raw substring check even though every
    word matches in order — comparing two strings built by the same
    tokenizer instead of raw-text-vs-tokenized-window is what makes the
    match word-boundary-exact rather than punctuation-exact.

    Lazy import so a caller that never touches quote-checking (most of
    this module's existing callers) never pays for reading the corpus
    off disk, and a checkout with no depositied books at all still works
    — `rag.load_core_chunks` degrades to `()` rather than raising.
    """
    from src.companion_corpus.rag import cached_core_chunks

    return tuple(" ".join(_WORD_RE.findall(chunk.text.casefold())) for chunk in cached_core_chunks())


def _quote_windows(text: str, min_words: int = QUOTE_MIN_WORDS) -> list[str]:
    words = _WORD_RE.findall(text.casefold())
    if len(words) < min_words:
        return []
    return [" ".join(words[i : i + min_words]) for i in range(len(words) - min_words + 1)]


def check_verbatim_quote(text: str, min_words: int = QUOTE_MIN_WORDS) -> bool:
    """True if `text` reproduces `min_words`+ consecutive words verbatim
    from any depositied core-catalog book chunk.

    Word-boundary tokenized (not a raw substring check) so punctuation
    and whitespace differences between the message and the source don't
    let a real quote slip past, and so a short shared phrase inside a
    much longer original sentence still triggers. Pure function, no I/O
    beyond the cached corpus load — safe to call on every generated
    message before it reaches a customer.
    """
    corpus = _corpus_word_sequences()
    if not corpus:
        return False
    for window in _quote_windows(text, min_words):
        if any(window in sequence for sequence in corpus):
            return True
    return False


def guard_payload(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    guarded = deepcopy(payload)
    if row.get("task") == "analyzer":
        return _guard_analyzer(row, guarded)
    return _guard_generator(row, guarded)


def _guard_analyzer(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    for objection in payload.get("objections") or []:
        alias = OBJECTION_ALIASES.get(str(objection.get("objection_type", "")))
        if alias:
            objection["objection_type"] = alias
    if high_risk_analyzer(row):
        payload["requires_human"] = True
        payload["observed_stage"] = "HUMAN_REVIEW"
        payload["recommended_moves"] = ["HANDOFF_TO_HUMAN"]
        payload["commitment_level"] = "UNKNOWN"
    return payload


def _guard_generator(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    approved = row.get("approved_move")
    if approved:
        payload["move"] = approved
    text = str(payload.get("message_text") or "")
    folded = text.casefold()
    if approved == "END_CONTACT":
        payload["used_safe_fallback"] = True
        if text.rstrip().endswith("?") or re.search(r"\bfollow up\b", text, flags=re.IGNORECASE):
            payload["message_text"] = END_CONTACT_CLOSE
        return payload
    if check_verbatim_quote(text):
        target = (row.get("target") or {}).get("message_text")
        if target and not check_verbatim_quote(target):
            payload["message_text"] = target
        else:
            payload["message_text"] = SAFE_NO_QUOTE
        return payload
    if any(phrase in folded for phrase in FFF):
        target = (row.get("target") or {}).get("message_text")
        payload["message_text"] = target or SAFE_NO_FFF
        return payload
    forbidden = list(row.get("forbidden_patterns") or [])
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in forbidden):
        target = (row.get("target") or {}).get("message_text")
        if target and not any(
            re.search(pattern, target, flags=re.IGNORECASE) for pattern in forbidden
        ):
            payload["message_text"] = target
        elif any("free extra" in pattern or "throw in" in pattern for pattern in forbidden):
            payload["message_text"] = SAFE_NO_GIFT
    return payload
