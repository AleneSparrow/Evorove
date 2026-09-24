from datetime import datetime, timezone

import pytest

from src.domain.sales import CustomerSalesProfile, SalesMove, SalesStage
from src.engine.sales_owner_facts import (
    MAX_FACT_CHARS,
    append_owner_business_fact,
    owner_listed_facts,
    pending_business_fact_request,
    with_pending_business_fact_request,
)


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _profile(**overrides: object) -> CustomerSalesProfile:
    values = {
        "business_id": "biz-1",
        "case_id": "case-1",
        "stage": SalesStage.FOLLOW_UP,
        "last_move": SalesMove.REQUEST_BUSINESS_FACT,
    }
    values.update(overrides)
    return CustomerSalesProfile(**values)  # type: ignore[arg-type]


def test_owner_fact_clears_pending_and_resumes_presentation() -> None:
    waiting = with_pending_business_fact_request(
        _profile(),
        reason_code="approved_presentation_knowledge_missing",
        requested_at=NOW,
    )
    pending = pending_business_fact_request(waiting)
    assert pending is not None
    assert pending["needed_for"] == "presentation"
    saved = append_owner_business_fact(
        waiting, "  We handle AC diagnostics for homes in this area.  ", now=NOW,
    )
    assert pending_business_fact_request(saved) is None
    assert saved.stage is SalesStage.NEEDS_CONFIRMED
    assert owner_listed_facts(saved) == (
        ("owner.fact.1", "We handle AC diagnostics for homes in this area."),
    )


def test_owner_fact_resumes_objection_handling() -> None:
    waiting = with_pending_business_fact_request(
        _profile(),
        reason_code="objection_answer_grounding_missing",
        requested_at=NOW,
    )
    saved = append_owner_business_fact(waiting, "We are set up for this kind of request.", now=NOW)
    assert saved.stage is SalesStage.OBJECTION_HANDLING


def test_blank_owner_fact_is_rejected() -> None:
    with pytest.raises(ValueError, match="required"):
        append_owner_business_fact(_profile(), "   ", now=NOW)


def test_owner_fact_is_capped() -> None:
    with pytest.raises(ValueError, match="at most"):
        append_owner_business_fact(_profile(), "x" * (MAX_FACT_CHARS + 1), now=NOW)
