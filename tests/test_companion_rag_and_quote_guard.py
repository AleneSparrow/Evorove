"""RAG retrieval over core-catalog books + the anti-verbatim-quote guard.

No network, no API key, no mlx. Degrades gracefully (tests are skipped,
not failed) on a checkout with no depositied private corpus.
"""

from __future__ import annotations

import pytest

from src.companion_corpus.known_titles import CORE_CATALOG_IDS
from src.companion_corpus.mouth_guard import check_verbatim_quote, guard_payload
from src.companion_corpus.rag import cached_core_chunks, format_context, retrieve

_CHUNKS = cached_core_chunks()
_LONG_CHUNK = next((c for c in _CHUNKS if len(c.text.split()) >= 20), None)

requires_corpus = pytest.mark.skipif(
    not _CHUNKS, reason="no depositied private sales corpus on this checkout"
)


@requires_corpus
def test_load_core_chunks_is_restricted_to_core_catalog_ids() -> None:
    assert all(chunk.catalog_id in CORE_CATALOG_IDS for chunk in _CHUNKS)
    assert len(_CHUNKS) > 100  # sanity: this is the full-book index, not a handful of rows


@requires_corpus
def test_retrieve_returns_relevant_chunks_ranked_by_overlap() -> None:
    sample = _CHUNKS[len(_CHUNKS) // 2]
    # Querying with the chunk's own leading words should surface that
    # chunk (or a close sibling with the same vocabulary) near the top —
    # this is lexical overlap, not semantic search, so the test only
    # asserts the mechanism works, not perfect relevance.
    query = " ".join(sample.text.split()[:12])
    hits = retrieve(query, top_k=5, chunks=_CHUNKS)
    assert hits
    assert all(hit.catalog_id in CORE_CATALOG_IDS for hit in hits)


def test_retrieve_on_empty_pool_returns_nothing() -> None:
    assert retrieve("anything", chunks=()) == []


def test_retrieve_on_blank_query_returns_nothing() -> None:
    pool = _CHUNKS if _CHUNKS else ()
    assert retrieve("   ", chunks=pool) == []


@requires_corpus
def test_format_context_labels_background_and_warns_against_quoting() -> None:
    hits = retrieve(_CHUNKS[0].text.split()[0], top_k=1, chunks=_CHUNKS)
    rendered = format_context(hits)
    assert "do not quote" in rendered.lower()


def test_format_context_on_no_hits_is_empty() -> None:
    assert format_context([]) == ""


@requires_corpus
def test_verbatim_quote_of_real_chunk_is_detected() -> None:
    # Eight consecutive words lifted straight out of a real depositied
    # chunk — this is exactly what the guard exists to catch.
    words = _LONG_CHUNK.text.split()
    quote = " ".join(words[:8])
    assert check_verbatim_quote(quote) is True


def test_paraphrase_is_not_flagged_as_a_quote() -> None:
    paraphrase = (
        "Leads going cold overnight is the actual problem worth fixing, not a generic pitch."
    )
    assert check_verbatim_quote(paraphrase) is False


@requires_corpus
def test_guard_rewrites_a_quoting_message_to_the_rows_own_target() -> None:
    words = _LONG_CHUNK.text.split()
    quote = " ".join(words[:10])
    row = {
        "task": "generator",
        "approved_move": "PRESENT_RELEVANT_VALUE",
        "forbidden_patterns": [],
        "target": {"message_text": "Leads sitting overnight is the gap this fixes."},
    }
    payload = {
        "move": "PRESENT_RELEVANT_VALUE",
        "message_text": f"Here's the thing: {quote}.",
        "knowledge_ids": [],
        "business_fact_ids": [],
        "customer_evidence_ids": [],
        "used_safe_fallback": False,
    }
    guarded = guard_payload(row, payload)
    assert check_verbatim_quote(guarded["message_text"]) is False
    assert guarded["message_text"] == row["target"]["message_text"]


@requires_corpus
def test_guard_falls_back_to_safe_text_when_no_clean_target_exists() -> None:
    words = _LONG_CHUNK.text.split()
    quote = " ".join(words[:10])
    row = {
        "task": "generator",
        "approved_move": "PRESENT_RELEVANT_VALUE",
        "forbidden_patterns": [],
        # No target at all -- the guard must not invent a clean one, it
        # must fall back to the deterministic safe text instead.
    }
    payload = {
        "move": "PRESENT_RELEVANT_VALUE",
        "message_text": quote,
        "knowledge_ids": [],
        "business_fact_ids": [],
        "customer_evidence_ids": [],
        "used_safe_fallback": False,
    }
    guarded = guard_payload(row, payload)
    assert check_verbatim_quote(guarded["message_text"]) is False
