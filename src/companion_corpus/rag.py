"""Local, offline retrieval over depositied core-catalog book text.

Retrieval only — never training, never a customer-facing message on its
own. Step 3 coverage pass (12 September 2026): the owner asked for the
companion to draw on the *full* text of depositied books, not only the
hand-picked rulebook paraphrases, but to never quote that text to a
customer. Fine-tuning weights on raw chapter text would make verbatim
memorization more likely on a corpus this small, not less — the
opposite of what was asked. This module is the other half of that
answer: full-text grounding through retrieval at generation time, kept
separate from the weights. `mouth_guard.check_verbatim_quote` is the
half that makes "never quote" a mechanical guarantee rather than a
prompt instruction, regardless of how a chunk reached the prompt.

Restricted to CORE_CATALOG_IDS — the same boundary `rulebook.py` and
`ingest.py` already enforce. No network, no API key, no embedding
model: this is cheap lexical (term-overlap) retrieval, not semantic
search. Good enough to surface a few plausibly relevant chunks; it is
a grounding aid, not a ranking product.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.companion_corpus.known_titles import CORE_CATALOG_IDS

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "docs" / "sales-knowledge" / "corpus-registry.json"
DEFAULT_EXTRACTED_DIR = REPO_ROOT / "private" / "sales-corpus" / ".extracted"

_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ]+")


@dataclass(frozen=True)
class CorpusChunk:
    catalog_id: str
    chunk: int
    text: str


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def load_core_chunks(
    registry_path: Path = DEFAULT_REGISTRY,
    extracted_dir: Path = DEFAULT_EXTRACTED_DIR,
) -> tuple[CorpusChunk, ...]:
    """Every chunk of every CORE_CATALOG_IDS deposit, read from the
    locally extracted text (gitignored, produced by `ingest.py`).

    Degrades to an empty tuple if the registry or an extracted file is
    missing — a repo with no deposits yet (or a CI checkout without the
    private corpus) gets no retrieval, not a crash.
    """
    if not registry_path.exists():
        return ()
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()
    chunks: list[CorpusChunk] = []
    for deposit in registry.get("deposits", []):
        catalog_id = deposit.get("catalog_id")
        sha256 = deposit.get("sha256")
        if catalog_id not in CORE_CATALOG_IDS or not sha256:
            continue
        path = extracted_dir / f"{sha256}.txt"
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for index, raw in enumerate(text.split("\x0c")):
            stripped = raw.strip()
            if stripped:
                chunks.append(CorpusChunk(catalog_id=catalog_id, chunk=index, text=stripped))
    return tuple(chunks)


@lru_cache(maxsize=1)
def cached_core_chunks() -> tuple[CorpusChunk, ...]:
    return load_core_chunks()


def retrieve(
    query: str,
    top_k: int = 3,
    chunks: tuple[CorpusChunk, ...] | None = None,
) -> list[CorpusChunk]:
    """Cheap lexical (term-overlap) retrieval — not semantic search.

    `chunks` is accepted so tests and callers with an already-loaded
    pool don't pay the disk-read cost again; omit it to use the cached
    full core-catalog index.
    """
    pool = chunks if chunks is not None else cached_core_chunks()
    if not pool:
        return []
    query_terms = set(_tokenize(query))
    if not query_terms:
        return []
    scored: list[tuple[int, CorpusChunk]] = []
    for item in pool:
        overlap = len(query_terms & set(_tokenize(item.text)))
        if overlap:
            scored.append((overlap, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def format_context(chunks: list[CorpusChunk]) -> str:
    """Render retrieved chunks as grounding context for a prompt.

    Explicitly labeled as background only, with a standing instruction
    not to quote it — the prompt-level half of "ground on it, never
    quote it." The guard (`mouth_guard.check_verbatim_quote`) is the
    mechanical half that does not depend on the model following this
    instruction.
    """
    if not chunks:
        return ""
    lines = [
        "BACKGROUND ONLY — do not quote, summarize in your own words if used, "
        "never copy a phrase of 8+ consecutive words from any line below:"
    ]
    for item in chunks:
        lines.append(f"- [{item.catalog_id}#{item.chunk}] {item.text[:600]}")
    return "\n".join(lines)
