"""Closed objection catalog: detection, cause, resolution, and knowledge match.

Methodology cards live in config/sales-knowledge. This module never invents a
discount, guarantee, or business fact. OTHER has no dedicated card on purpose:
the trained model still diagnoses and answers it from customer evidence and
Business DNA. Missing card is not a handoff.
"""

from __future__ import annotations

import re
from typing import Iterable

from src.domain.sales import (
    ObjectionStatus,
    ObjectionType,
    SalesKnowledgeCard,
    SalesMove,
    SalesObjection,
)

_OBJECTION_TYPE_WHEN = re.compile(r"objection_type\s*=\s*([A-Z_]+)")

_DETECTION: tuple[tuple[ObjectionType, tuple[re.Pattern[str], ...]], ...] = (
    (
        ObjectionType.AUTHORITY,
        (
            re.compile(r"\b(?:ask(?: my)?|talk to|check with|run (?:this|it) by)\s+(?:my )?(?:wife|husband|spouse|partner|boss|manager)\b", re.I),
            re.compile(r"\bnot (?:my|the) (?:decision|call)\b", re.I),
            re.compile(r"\bsomeone else (?:needs?|has) to (?:decide|approve)\b", re.I),
        ),
    ),
    (
        ObjectionType.COMPETITOR,
        (
            re.compile(r"\b(?:another|other) (?:company|vendor|quote|option)s?\b", re.I),
            re.compile(r"\bgetting (?:a )?quotes?\b", re.I),
            re.compile(r"\bcompar(?:e|ing) (?:options|companies|quotes)\b", re.I),
        ),
    ),
    (
        ObjectionType.PRICE,
        (
            re.compile(r"\b(?:too )?(?:expensive|pricey)\b", re.I),
            re.compile(r"\bmore than I (?:expected|wanted|can)\b", re.I),
            re.compile(r"\b(?:can't|cannot|can not) afford\b", re.I),
            re.compile(r"\b(?:that's|that is) (?:a lot|too much)\b", re.I),
            re.compile(r"\bcost(?:s|ing)? too much\b", re.I),
        ),
    ),
    (
        ObjectionType.TRUST,
        (
            re.compile(r"\bhow do I (?:even )?know\b", re.I),
            re.compile(r"\b(?:does this|will this) actually work\b", re.I),
            re.compile(r"\b(?:scam|just another (?:vendor )?pitch)\b", re.I),
            re.compile(r"\b(?:reviews?|references?|proof) that (?:this|it) works\b", re.I),
        ),
    ),
    (
        ObjectionType.TIMING,
        (
            re.compile(r"\bnot (?:going to start|starting) anything (?:new )?(?:until|this)\b", re.I),
            re.compile(r"\b(?:next quarter|next month|after the holidays)\b", re.I),
            re.compile(r"\bnot (?:right )?now\b", re.I),
            re.compile(r"\btoo busy (?:right now|this (?:week|month))\b", re.I),
        ),
    ),
    (
        ObjectionType.NEED_TO_THINK,
        (
            re.compile(r"\blet me think\b", re.I),
            re.compile(r"\bget back to you\b", re.I),
            re.compile(r"\bneed to think\b", re.I),
            re.compile(r"\bsleep on it\b", re.I),
        ),
    ),
    (
        ObjectionType.FIT,
        (
            re.compile(r"\bnot (?:sure this is |a good )?for me\b", re.I),
            re.compile(r"\b(?:wrong|not the) (?:service|fit)\b", re.I),
            re.compile(r"\byou don'?t (?:do|handle|offer) that\b", re.I),
        ),
    ),
    (
        ObjectionType.OTHER,
        (
            re.compile(r"\bnot comfortable (?:with )?(?:this|that|it)\b", re.I),
            re.compile(r"\bsomething (?:about this )?(?:doesn'?t|does not) (?:sit right|feel right)\b", re.I),
            re.compile(r"\bi (?:just )?have (?:a |some )?concerns?\b", re.I),
            re.compile(r"\bnot sure (?:about|i (?:like|want)) (?:this|that)\b", re.I),
        ),
    ),
)

_CAUSE_PATTERNS: dict[ObjectionType, tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]] = {
    ObjectionType.PRICE: (
        ("value", (
            re.compile(r"\bworth it\b", re.I),
            re.compile(r"\bpay off\b", re.I),
            re.compile(r"\bvalue\b", re.I),
            re.compile(r"\bjustify\b", re.I),
        )),
        ("affordability", (
            re.compile(r"\bbudget\b", re.I),
            re.compile(r"\bafford\b", re.I),
            re.compile(r"\bcan't pay\b", re.I),
            re.compile(r"\btotal\b", re.I),
        )),
        ("timing", (
            re.compile(r"\blater\b", re.I),
            re.compile(r"\bnot now\b", re.I),
            re.compile(r"\bthis month\b", re.I),
        )),
    ),
    ObjectionType.TRUST: (
        ("proof", (
            re.compile(r"\bproof\b", re.I),
            re.compile(r"\breviews?\b", re.I),
            re.compile(r"\bexamples?\b", re.I),
            re.compile(r"\bsee (?:it|this) work\b", re.I),
        )),
        ("legitimacy", (
            re.compile(r"\breal\b", re.I),
            re.compile(r"\blegit\b", re.I),
            re.compile(r"\btrust\b", re.I),
        )),
    ),
    ObjectionType.TIMING: (
        ("constraint", (
            re.compile(r"\bbusy\b", re.I),
            re.compile(r"\bschedule\b", re.I),
            re.compile(r"\buntil\b", re.I),
        )),
        ("uncertainty", (
            re.compile(r"\bnot sure\b", re.I),
            re.compile(r"\bmaybe later\b", re.I),
        )),
    ),
    ObjectionType.FIT: (
        ("mismatch", (
            re.compile(r"\bmismatch\b", re.I),
            re.compile(r"\bwrong\b", re.I),
            re.compile(r"\bnot what I\b", re.I),
        )),
    ),
    ObjectionType.AUTHORITY: (
        ("other_decision_maker", (
            re.compile(r"\bwife\b", re.I),
            re.compile(r"\bhusband\b", re.I),
            re.compile(r"\bpartner\b", re.I),
            re.compile(r"\bboss\b", re.I),
            re.compile(r"\bsomeone else\b", re.I),
        )),
    ),
    ObjectionType.COMPETITOR: (
        ("comparison", (
            re.compile(r"\bprice\b", re.I),
            re.compile(r"\bspeed\b", re.I),
            re.compile(r"\bquality\b", re.I),
            re.compile(r"\bcomparing\b", re.I),
        )),
    ),
    ObjectionType.NEED_TO_THINK: (
        ("unclear_next_step", (
            re.compile(r"\bnext step\b", re.I),
            re.compile(r"\bclearer\b", re.I),
            re.compile(r"\bmore (?:info|information|detail)\b", re.I),
        )),
        ("need_time", (
            re.compile(r"\btime\b", re.I),
            re.compile(r"\bthink\b", re.I),
            re.compile(r"\blater\b", re.I),
        )),
    ),
    ObjectionType.OTHER: (
        ("stated_concern", (
            re.compile(r"\b(?:messy|confusing|unclear|complicated|overwhelming)\b", re.I),
            re.compile(r"\bthe (?:whole |entire )?(?:process|thing|setup)\b", re.I),
            re.compile(r"\bjust (?:not sure|uneasy|worried)\b", re.I),
        )),
    ),
}

_RESOLUTION = re.compile(
    r"\b(?:that (?:helps|makes sense|addresses it)|got it|ok(?:ay)?(?: then)?|"
    r"yes(?:,? (?:that helps|please|let'?s|book))?|sounds (?:good|fair))\b",
    re.I,
)
_DEFERRAL = re.compile(
    r"\b(?:(?:need|want|give me) (?:some )?time|maybe later|(?:follow(?:ing)? up|come back to (?:this|that|it)) later|"
    r"not (?:right )?now|get back to (?:you|me)|later(?: please)?)\b",
    re.I,
)
_ZIP_ONLY = re.compile(r"^\s*\d{5}(?:-\d{4})?\s*$")
_CAUSE_ACK = re.compile(r"^(?:yes|yep|yeah|no|nope|ok|okay|sure|idk|dunno)[.!?]*$", re.I)

DIAGNOSE_PROMPTS: dict[ObjectionType, str] = {
    ObjectionType.PRICE: (
        "When you say the cost is a concern, is that the total budget, "
        "or whether the result will justify it?"
    ),
    ObjectionType.TRUST: "What would you need to see to feel confident taking the next step?",
    ObjectionType.TIMING: "Is the timing a hard constraint, or would a later next step work better?",
    ObjectionType.FIT: "Which part feels like a mismatch with what you need help with?",
    ObjectionType.AUTHORITY: "Who else needs to be part of this decision?",
    ObjectionType.COMPETITOR: "What matters most in that comparison for the problem you described?",
    ObjectionType.NEED_TO_THINK: (
        "No rush. What would help you decide — a clearer next step now, "
        "or time with a follow-up later?"
    ),
    ObjectionType.OTHER: "What feels like the main thing in the way right now?",
}


def first_match_excerpt(patterns: Iterable[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        matched = pattern.search(text or "")
        if matched is None:
            continue
        excerpt = matched.group(0).strip()
        if excerpt:
            return excerpt
    return None


def detect_objection_type(text: str) -> tuple[ObjectionType, str] | None:
    for objection_type, patterns in _DETECTION:
        excerpt = first_match_excerpt(patterns, text)
        if excerpt is not None:
            return objection_type, excerpt
    return None


def infer_objection_cause(objection_type: ObjectionType, text: str) -> tuple[str, str] | None:
    for cause, patterns in _CAUSE_PATTERNS.get(objection_type, ()):
        excerpt = first_match_excerpt(patterns, text)
        if excerpt is not None:
            return cause, excerpt
    return None


def stated_concern_excerpt(text: str) -> str | None:
    """Verbatim cause for OTHER after diagnosis. Not a booking signal or zip."""

    stripped = (text or "").strip()
    if len(stripped) < 8:
        return None
    if _ZIP_ONLY.match(stripped) or _CAUSE_ACK.match(stripped):
        return None
    return stripped[:80]


def looks_like_resolution(text: str) -> bool:
    return _RESOLUTION.search(text or "") is not None


def looks_like_deferral(text: str) -> bool:
    return _DEFERRAL.search(text or "") is not None


def matching_knowledge(
    cards: tuple[SalesKnowledgeCard, ...],
    objection: SalesObjection | None,
) -> tuple[SalesKnowledgeCard, ...]:
    if objection is None:
        return ()
    wanted = f"objection_type={objection.objection_type.value}"
    matched: list[SalesKnowledgeCard] = []
    for card in cards:
        if any(_applies(item, wanted, objection.objection_type) for item in card.applicable_when):
            matched.append(card)
    return tuple(matched)


def _applies(rule: str, wanted: str, objection_type: ObjectionType) -> bool:
    stripped = rule.strip()
    if stripped == wanted:
        return True
    parsed = _OBJECTION_TYPE_WHEN.search(stripped)
    return parsed is not None and parsed.group(1) == objection_type.value


def diagnose_prompt(objection: SalesObjection | None) -> str:
    if objection is None:
        return DIAGNOSE_PROMPTS[ObjectionType.OTHER]
    return DIAGNOSE_PROMPTS.get(objection.objection_type, DIAGNOSE_PROMPTS[ObjectionType.OTHER])


def answer_prompt(cards: tuple[SalesKnowledgeCard, ...], fallback: str) -> str:
    for card in cards:
        for example in card.approved_examples:
            if example.strip():
                return example.strip()
    return fallback


def mark_addressed(objection: SalesObjection | None, move: SalesMove) -> SalesObjection | None:
    if objection is None or move is not SalesMove.ANSWER_OBJECTION:
        return objection
    if objection.status in {ObjectionStatus.RESOLVED, ObjectionStatus.DEFERRED}:
        return objection
    return SalesObjection(
        objection.objection_type,
        ObjectionStatus.ADDRESSED,
        objection.evidence,
        objection.cause,
    )
