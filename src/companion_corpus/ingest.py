"""Scan owner-deposited books, write registry + derived JSONL. Never trains."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ai.sales_models import SalesTurnAnalysisOutput
from src.ai.sales_response_models import SalesResponseOutput, check_move_matches_approved
from src.domain.sales import SalesMove

from .derived_rows import rows_for_title
from .extract import (
    UnsupportedCorpusFile,
    extract_pages,
    file_sha256,
    locate_markers,
    write_extracted_copy,
)
from .known_titles import BOOK_SUFFIXES, CORE_CATALOG_IDS, SKIP_FILENAMES, KnownTitle, corpus_lane, match_known_title

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "private" / "sales-corpus"
DEFAULT_REGISTRY = REPO_ROOT / "docs" / "sales-knowledge" / "corpus-registry.json"
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "sales-knowledge" / "corpus-manifest-step1.md"
DEFAULT_DERIVED_DIR = REPO_ROOT / "evals" / "companion_step1" / "data" / "derived"
DEFAULT_INDEX = REPO_ROOT / "evals" / "companion_step1" / "derived" / "deposit-index.json"
DEFAULT_CARDS = REPO_ROOT / "evals" / "companion_step1" / "derived" / "candidate-cards-from-deposits.json"

DEPOSITED_START = "<!-- corpus-ingest:deposited:start -->"
DEPOSITED_END = "<!-- corpus-ingest:deposited:end -->"
READY_START = "<!-- corpus-ingest:ready:start -->"
READY_END = "<!-- corpus-ingest:ready:end -->"

LICENCE_VALUES = frozenset({"purchase", "publisher-licence", "my-copy", "public-domain", "cc"})


def ingest_sales_corpus(
    *,
    corpus_dir: Path | None = None,
    registry_path: Path | None = None,
    manifest_path: Path | None = None,
    derived_dir: Path | None = None,
    index_path: Path | None = None,
    cards_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    corpus_dir = corpus_dir or DEFAULT_CORPUS
    registry_path = registry_path or DEFAULT_REGISTRY
    manifest_path = manifest_path or DEFAULT_MANIFEST
    derived_dir = derived_dir or DEFAULT_DERIVED_DIR
    index_path = index_path or DEFAULT_INDEX
    cards_path = cards_path or DEFAULT_CARDS
    stamp = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()

    incoming = corpus_dir / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    extracted_root = corpus_dir / ".extracted"
    extracted_root.mkdir(parents=True, exist_ok=True)

    deposits: list[dict[str, Any]] = []
    errors: list[str] = []
    analyzer_rows: list[dict] = []
    generator_rows: list[dict] = []
    card_overlays: list[dict] = []

    for path in _iter_book_files(corpus_dir):
        try:
            record, extra_an, extra_gen, overlay = _ingest_one(path, corpus_dir, extracted_root)
        except UnsupportedCorpusFile as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        deposits.append(record)
        _extend_unique(analyzer_rows, extra_an)
        _extend_unique(generator_rows, extra_gen)
        card_overlays.extend(overlay)

    mapped = [row for row in deposits if row.get("catalog_id")]
    mapped_ids = {row["catalog_id"] for row in mapped}
    core_ids = {catalog_id for catalog_id in mapped_ids if catalog_id in CORE_CATALOG_IDS}
    ready = bool(core_ids)
    core_closed = (
        ("spin-selling", "SPIN Selling"),
        ("challenger-sale", "The Challenger Sale"),
        ("influence", "Influence"),
        ("never-split-the-difference", "Never Split the Difference"),
        ("fanatical-prospecting", "Fanatical Prospecting"),
    )
    status = {
        "updated_at": stamp,
        "cycle": 2,
        "training_job_started": False,
        "cards_approved": False,
        "ready_for_step2_training": ready,
        "owner_zip_is_positive_sft": False,
        "deposited_files": len(deposits),
        "mapped_known_titles": sorted(mapped_ids),
        "sft_core_titles": sorted(core_ids),
        "archive_mapped_titles": sorted(mapped_ids - core_ids),
        "unmapped_files": [row["filename"] for row in deposits if not row.get("catalog_id")],
        "errors": errors,
        "deposits": deposits,
        "needs_licence_until_deposited": [
            name for catalog_id, name in core_closed if catalog_id not in mapped_ids
        ],
        "next_owner_step": (
            "Corpus stays open: drop more purchased files in private/sales-corpus/incoming/ "
            "and re-run ingest anytime. SFT rows come from core titles only. "
            "Step 2 training is a separate owner decision; ingest never starts a job."
        ),
    }

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    derived_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(derived_dir / "analyzer_from_corpus.jsonl", analyzer_rows)
    _write_jsonl(derived_dir / "generator_from_corpus.jsonl", generator_rows)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_payload = {
        "updated_at": stamp,
        "note": "No book text. Hashes, page counts, marker page hits only.",
        "deposits": [
            {
                "filename": row["filename"],
                "sha256": row["sha256"],
                "page_count": row["page_count"],
                "catalog_id": row.get("catalog_id"),
                "lane": row.get("lane"),
                "marker_pages": row.get("marker_pages") or {},
                "licence": row.get("licence"),
            }
            for row in deposits
        ],
    }
    index_path.write_text(json.dumps(index_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from .rulebook import candidate_cards

    existing_ids = {
        card.get("knowledge_id")
        for card in card_overlays
        if isinstance(card, dict) and card.get("knowledge_id")
    }
    for card in candidate_cards():
        if card["catalog_id"] not in core_ids:
            continue
        if card["knowledge_id"] in existing_ids:
            continue
        card_overlays.append(card)
        existing_ids.add(card["knowledge_id"])
    cards_path.write_text(json.dumps(card_overlays, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if manifest_path.exists():
        _patch_manifest(manifest_path, deposits, ready, stamp)

    return status


def _extend_unique(dst: list[dict], extra: list[dict]) -> None:
    seen = {row.get("id") for row in dst}
    for row in extra:
        row_id = row.get("id")
        if row_id in seen:
            continue
        dst.append(row)
        seen.add(row_id)


def corpus_status(registry_path: Path | None = None) -> dict[str, Any]:
    path = registry_path or DEFAULT_REGISTRY
    if not path.exists():
        return {
            "ready_for_step2_training": False,
            "deposited_files": 0,
            "next_owner_step": "Run python scripts/ingest_sales_corpus.py after dropping books.",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_book_files(corpus_dir: Path) -> list[Path]:
    incoming = corpus_dir / "incoming"
    files: list[Path] = []
    search_roots = [incoming]
    if incoming.resolve() != corpus_dir.resolve():
        # Also accept a purchased file dropped next to README (not nested docs).
        search_roots.append(corpus_dir)
    seen: set[Path] = set()
    for root in search_roots:
        if not root.is_dir():
            continue
        iterator = root.rglob("*") if root == incoming else root.iterdir()
        for path in sorted(iterator):
            if path in seen or not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if ".extracted" in path.parts:
                continue
            if path.name.casefold() in SKIP_FILENAMES:
                continue
            if path.suffix.lower() not in BOOK_SUFFIXES:
                continue
            if root == corpus_dir and path.suffix.lower() in {".md", ".html", ".htm"}:
                continue
            seen.add(path)
            files.append(path)
    return files


def _ingest_one(
    path: Path, corpus_dir: Path, extracted_root: Path
) -> tuple[dict[str, Any], list[dict], list[dict], list[dict]]:
    sidecar = _load_or_create_sidecar(path)
    digest = file_sha256(path)
    pages = extract_pages(path)
    write_extracted_copy(pages, extracted_root / f"{digest}.txt")
    known = match_known_title(path.name)
    marker_pages = locate_markers(pages, known.markers) if known else {}
    provenance = "title-only"
    if known and marker_pages:
        provenance = "page-located"
    elif known:
        provenance = "deposited-copy"

    record: dict[str, Any] = {
        "filename": path.name,
        "relative_path": str(path.relative_to(corpus_dir)),
        "sha256": digest,
        "byte_size": path.stat().st_size,
        "page_count": len(pages),
        "licence": sidecar.get("licence", "my-copy"),
        "attestation": sidecar.get("attestation"),
        "title": sidecar.get("title") or (known.title if known else path.stem),
        "author": sidecar.get("author") or (known.author if known else ""),
        "year": sidecar.get("year") if sidecar.get("year") is not None else (known.year if known else None),
        "catalog_id": known.catalog_id if known else None,
        "lane": corpus_lane(known.catalog_id if known else None),
        "proposed_use": known.proposed_use if known else "unmapped; owner should name the methodology",
        "provenance": provenance,
        "marker_pages": marker_pages,
        "knowledge_ids": list(known.knowledge_ids) if known else [],
        "status": "candidate",
        "extracted_to": f".extracted/{digest}.txt",
    }

    analyzer: list[dict] = []
    generator: list[dict] = []
    overlays: list[dict] = []
    if known is not None:
        analyzer, generator = rows_for_title(known)
        _validate_rows(analyzer, generator)
        overlays.append(_card_overlay(known, record))
    return record, analyzer, generator, overlays


def _load_or_create_sidecar(path: Path) -> dict[str, Any]:
    sidecar_path = path.with_suffix(path.suffix + ".licence.json")
    if sidecar_path.exists():
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        licence = str(data.get("licence") or "my-copy")
        if licence not in LICENCE_VALUES:
            raise UnsupportedCorpusFile(
                f"licence sidecar {sidecar_path.name} has unknown licence {licence!r}"
            )
        return data
    known = match_known_title(path.name)
    stub = {
        "licence": "my-copy",
        "attestation": (
            "I legally own this copy and may use it to derive short training rules. "
            "Dropping the file in private/sales-corpus is that attestation."
        ),
        "title": known.title if known else path.stem.replace("_", " "),
        "author": known.author if known else "",
        "year": known.year if known else None,
    }
    sidecar_path.write_text(json.dumps(stub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return stub


def _card_overlay(known: KnownTitle, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "candidate",
        "version": 0,
        "catalog_id": known.catalog_id,
        "knowledge_ids": list(known.knowledge_ids),
        "source": {
            "title": known.title,
            "author": known.author,
            "location": record["filename"],
            "provenance_confidence": record["provenance"],
            "marker_pages": record["marker_pages"],
        },
        "note": "Overlay only. Do not import or approve. Spec 0.4 still binds.",
        "posture_0_4": "scarcity stays negative without a DNA slot fact; Feel-Felt-Found is never a positive",
    }


def _validate_rows(analyzer: list[dict], generator: list[dict]) -> None:
    for row in analyzer:
        target = SalesTurnAnalysisOutput.model_validate(row["target"])
        message = row["customer_message"]
        for signal in target.signals:
            if signal.evidence not in message:
                raise ValueError(f"{row['id']}: signal evidence not in message")
        for objection in target.objections:
            if objection.evidence not in message:
                raise ValueError(f"{row['id']}: objection evidence not in message")
    for row in generator:
        output = SalesResponseOutput.model_validate(row["target"])
        approved = SalesMove(row["approved_move"])
        if check_move_matches_approved(output, approved):
            raise ValueError(f"{row['id']}: move does not echo approved_move")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _patch_manifest(
    manifest_path: Path, deposits: list[dict[str, Any]], ready: bool, stamp: str
) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    deposited_body = _deposited_markdown(deposits, stamp)
    ready_body = (
        f"**Yes (corpus only, {stamp}).** At least one **core** conversation-sales title is deposited. "
        "Archive files stay registered and do not unlock SFT. "
        "The incoming folder stays open — drop more purchased files and re-run ingest anytime. "
        "Ingest still does **not** start a training job. Review derived JSONL, then Step 2 is a separate owner decision.\n"
        if ready
        else f"**No ({stamp}).** Closed-access copies the owner wants in the fine-tune are not deposited yet, "
        "or ingest reported errors. The owner zip is not a positive SFT set. Drop files in "
        "`private/sales-corpus/incoming/` and run `python scripts/ingest_sales_corpus.py`.\n"
    )
    text = _replace_block(text, DEPOSITED_START, DEPOSITED_END, deposited_body)
    text = _replace_block(text, READY_START, READY_END, ready_body)
    manifest_path.write_text(text, encoding="utf-8")


def _deposited_markdown(deposits: list[dict[str, Any]], stamp: str) -> str:
    if not deposits:
        return (
            f"_No book files scanned at {stamp}. Put purchased PDFs in "
            "`private/sales-corpus/incoming/`._\n"
        )
    lines = [
        f"Scanned {stamp}. Book bytes stay gitignored. This table has filenames only.\n",
        "",
        "| File | Title | Licence | Catalog | Pages | Provenance | Use |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in deposits:
        lines.append(
            "| `{filename}` | {title} | {licence} | {catalog} | {pages} | {prov} | {use} |".format(
                filename=row["filename"],
                title=row["title"],
                licence=row["licence"],
                catalog=row.get("catalog_id") or "unmapped",
                pages=row["page_count"],
                prov=row["provenance"],
                use=row["proposed_use"].replace("|", "/"),
            )
        )
    return "\n".join(lines) + "\n"


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    if start not in text or end not in text:
        return text
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return f"{before}{start}\n{body}{end}{after}"
