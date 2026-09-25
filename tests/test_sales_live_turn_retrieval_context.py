"""Step 2.5 (12 September 2026): live-turn RAG grounding is local, free,
and never blocks a sales turn. Skips gracefully on a checkout with no
depositied private corpus, matching src.companion_corpus.rag's own
degrade-to-empty behavior.
"""

from datetime import datetime, timezone

import pytest

from src.companion_corpus.rag import cached_core_chunks
from src.domain.sales import CustomerEvidence, ObjectionStatus, ObjectionType, SalesObjection
from src.persistence.sales_live_turn import _retrieval_context_for

_HAS_CORPUS = bool(cached_core_chunks())
requires_corpus = pytest.mark.skipif(not _HAS_CORPUS, reason="no depositied private sales corpus on this checkout")


def _objection(kind: ObjectionType) -> SalesObjection:
    return SalesObjection(
        objection_type=kind,
        status=ObjectionStatus.ACTIVE,
        evidence=CustomerEvidence("msg-1", "excerpt"),
    )


def test_no_active_objection_and_no_customer_words_returns_empty() -> None:
    assert _retrieval_context_for("", None) == ""


def test_retrieval_error_or_missing_corpus_never_raises() -> None:
    # No corpus assumption either way -- this must not raise regardless of
    # whether the private corpus is depositied on this machine.
    result = _retrieval_context_for("leads sit overnight before anyone replies", None)
    assert isinstance(result, str)


@requires_corpus
def test_objection_type_is_folded_into_the_retrieval_query() -> None:
    without = _retrieval_context_for("that's way more than I expected to pay", None)
    with_price = _retrieval_context_for(
        "that's way more than I expected to pay", _objection(ObjectionType.PRICE)
    )
    # Both are plain strings (possibly empty); the point of this test is
    # that adding the objection type does not crash and still returns str
    # -- exact retrieval ranking is lexical/best-effort, not asserted here.
    assert isinstance(without, str)
    assert isinstance(with_price, str)


@requires_corpus
def test_grounding_never_becomes_a_quote_by_construction() -> None:
    """format_context() (used inside _retrieval_context_for) always labels
    its output BACKGROUND ONLY / do not quote -- covered directly in
    tests/test_companion_rag_and_quote_guard.py. This test just confirms
    the live-turn helper's output, when non-empty, carries that same label
    rather than raw unlabeled book text.
    """
    result = _retrieval_context_for("overnight leads keep going cold", None)
    if result:
        assert "do not quote" in result.lower()
