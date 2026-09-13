"""Pick one activated owner material for PRESENT_RELEVANT_VALUE.

The library is facts, not generated ads. The server chooses a single item
from the activated snapshot. Drafts are ignored until Refresh.
"""

from __future__ import annotations

import re

from src.domain.marketing_materials import SnapshotItem, decode_snapshot
from src.domain.sales import CustomerSalesProfile
from src.persistence.repositories import UnitOfWork

_STOP = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "your", "you",
    "are", "was", "were", "have", "has", "not", "but", "our", "any",
    "can", "will", "just", "about", "into", "than", "then", "them",
})
_WORD = re.compile(r"[a-z0-9]{3,}")
_KIND_BONUS = {"offer": 2, "notes": 1, "media": 0}


def pick_activated_owner_material(
    uow: UnitOfWork,
    business_id: str,
    profile: CustomerSalesProfile | None,
) -> tuple[str, str] | None:
    guidance = uow.marketing_materials.get_guidance(business_id)
    if guidance is None:
        return None
    chosen = pick_relevant_snapshot_item(
        decode_snapshot(guidance.snapshot_text),
        problem=profile.current_problem if profile is not None else None,
        outcome=profile.desired_outcome if profile is not None else None,
        goal=profile.customer_goal if profile is not None else None,
    )
    if chosen is None:
        return None
    text = chosen.usable_fact_text()
    if text is None:
        return None
    fact_id = f"owner.material.{chosen.asset_id}"[:64]
    return fact_id, text


def pick_relevant_snapshot_item(
    items: tuple[SnapshotItem, ...],
    *,
    problem: str | None,
    outcome: str | None,
    goal: str | None,
) -> SnapshotItem | None:
    usable = tuple(item for item in items if item.usable_fact_text() is not None)
    if not usable:
        return None
    query = _tokens(" ".join(part for part in (problem, outcome, goal) if part))
    ranked = sorted(
        usable,
        key=lambda item: (
            len(query & _tokens(f"{item.title} {item.body_text}")) if query else 0,
            _KIND_BONUS.get(item.kind, 0),
        ),
        reverse=True,
    )
    if query and len(query & _tokens(f"{ranked[0].title} {ranked[0].body_text}")) == 0:
        offers = tuple(item for item in usable if item.kind == "offer")
        return offers[0] if offers else usable[0]
    return ranked[0]


def _tokens(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.casefold()) if word not in _STOP}
