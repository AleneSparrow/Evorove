"""Owner-supplied business facts: ask the business, keep the customer.

When DNA has no name/description facts and no approved cards, the engine
asks the owner for a fact instead of handing the customer to a person.
Prices, discounts, and guarantees still cannot be invented for the customer.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Mapping

from src.domain.sales import CustomerSalesProfile, SalesStage


OWNER_FACTS_KEY = "owner_business_facts"
PENDING_KEY = "pending_business_fact_request"
MAX_FACT_CHARS = 500


def owner_listed_facts(profile: CustomerSalesProfile) -> tuple[tuple[str, str], ...]:
    raw = profile.metadata.get(OWNER_FACTS_KEY)
    if not isinstance(raw, list):
        return ()
    facts: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        fact_id = item.get("business_fact_id")
        text = item.get("text")
        if isinstance(fact_id, str) and fact_id.strip() and isinstance(text, str) and text.strip():
            facts.append((fact_id.strip(), text.strip()))
    return tuple(facts)


def pending_business_fact_request(profile: CustomerSalesProfile) -> dict[str, Any] | None:
    raw = profile.metadata.get(PENDING_KEY)
    if not isinstance(raw, Mapping):
        return None
    needed_for = raw.get("needed_for")
    reason_code = raw.get("reason_code")
    if not isinstance(needed_for, str) or not needed_for.strip():
        return None
    if not isinstance(reason_code, str) or not reason_code.strip():
        return None
    requested_at = raw.get("requested_at")
    resume_stage = raw.get("resume_stage")
    return {
        "needed_for": needed_for.strip(),
        "reason_code": reason_code.strip(),
        "requested_at": requested_at if isinstance(requested_at, str) else None,
        "resume_stage": resume_stage if isinstance(resume_stage, str) else None,
    }


def needed_for_from_reason(reason_code: str) -> str:
    if reason_code == "objection_answer_grounding_missing":
        return "objection_answer"
    return "presentation"


def resume_stage_from_reason(reason_code: str) -> SalesStage:
    if reason_code == "objection_answer_grounding_missing":
        return SalesStage.OBJECTION_HANDLING
    return SalesStage.NEEDS_CONFIRMED


def with_pending_business_fact_request(
    profile: CustomerSalesProfile,
    *,
    reason_code: str,
    requested_at: datetime,
) -> CustomerSalesProfile:
    metadata = dict(profile.metadata)
    metadata[PENDING_KEY] = {
        "needed_for": needed_for_from_reason(reason_code),
        "reason_code": reason_code,
        "requested_at": requested_at.isoformat(),
        "resume_stage": resume_stage_from_reason(reason_code).value,
    }
    return replace(profile, metadata=metadata)


def append_owner_business_fact(
    profile: CustomerSalesProfile,
    text: str,
    *,
    now: datetime,
) -> CustomerSalesProfile:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("business fact text is required")
    if len(cleaned) > MAX_FACT_CHARS:
        raise ValueError(f"business fact text must be at most {MAX_FACT_CHARS} characters")
    pending = pending_business_fact_request(profile)
    raw_facts = profile.metadata.get(OWNER_FACTS_KEY)
    facts: list[dict[str, str]] = []
    if isinstance(raw_facts, list):
        for item in raw_facts:
            if isinstance(item, Mapping):
                facts.append(dict(item))
    fact_id = f"owner.fact.{len(facts) + 1}"
    facts.append({
        "business_fact_id": fact_id,
        "text": cleaned,
        "supplied_at": now.isoformat(),
    })
    metadata = dict(profile.metadata)
    metadata[OWNER_FACTS_KEY] = facts
    metadata.pop(PENDING_KEY, None)
    resume_stage = profile.stage
    if pending is not None and pending.get("resume_stage"):
        try:
            resume_stage = SalesStage(pending["resume_stage"])
        except ValueError:
            resume_stage = profile.stage
    return replace(profile, metadata=metadata, stage=resume_stage)
