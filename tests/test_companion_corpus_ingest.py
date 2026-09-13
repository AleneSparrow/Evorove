"""Ingest owner-deposited books into companion Step 1 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from src.companion_corpus.extract import extract_pages, locate_markers
from src.companion_corpus.derived_rows import rows_for_title
from src.companion_corpus.ingest import ingest_sales_corpus
from src.companion_corpus.known_titles import CORE_CATALOG_IDS, KNOWN_TITLES, match_known_title
from src.ai.sales_models import SalesTurnAnalysisOutput
from src.ai.sales_response_models import SalesResponseOutput, check_move_matches_approved
from src.domain.sales import SalesMove


def test_match_known_title_from_filename() -> None:
    assert match_known_title("SPIN_Selling.pdf").catalog_id == "spin-selling"
    assert match_known_title("Never Split the Difference.epub").catalog_id == (
        "never-split-the-difference"
    )
    assert match_known_title("Нил Рекхэм   СПИН-продажи.fb2").catalog_id == "spin-selling"
    assert match_known_title("Мэттью_Диксон,_Брент_Адамсон_Чемпионы_продаж.epub").catalog_id == (
        "challenger-sale"
    )
    assert match_known_title("Крис_Восс_Никаких_компромиссов_Веди_переговоры.fb2").catalog_id == (
        "never-split-the-difference"
    )
    assert match_known_title(
        "Роберт_Бено_Чалдини_Influence_The_Psychology_of_Persuasion.fb2"
    ).catalog_id == "influence"
    assert match_known_title(
        "Дональд_Миллер_Метод_StoryBrand_2_0_Расскажите_о_своем_бренде.fb2"
    ).catalog_id == "storybrand-2"
    assert match_known_title(
        "Дональд_Миллер_Метод_StoryBrand_Расскажите_о_своем_бренде_так,.epub"
    ).catalog_id == "storybrand"
    assert match_known_title(
        "Джеб_Блаунт_Фанатичные_продажи_Принципы_экстремально_быстрого.epub"
    ).catalog_id == "fanatical-prospecting"
    assert match_known_title(
        "Адам_Грант_Брать_или_отдавать_Новый_взгляд.fb2"
    ).catalog_id == "give-and-take"
    assert match_known_title(
        "Кейт_Феррацци_Никогда_не_ешьте_в_одиночку.fb2"
    ).catalog_id == "never-eat-alone"
    assert match_known_title("Даниэль Канеман   Thinking, Fast and Slow.epub").catalog_id == (
        "thinking-fast-slow"
    )
    assert match_known_title("Ричард_Талер_Nudge_Архитектура_выбора.fb2").catalog_id == "nudge"
    assert match_known_title(
        "Джеффри А. Мур — Преодоление пропасти. Маркетинг и продажа хайтек-товаров.fb2"
    ).catalog_id == "crossing-the-chasm"
    assert match_known_title(
        "Harvard Business Review (HBR) — Продажи.epub"
    ).catalog_id == "hbr-sales"
    assert match_known_title(
        "Николай Юрьевич Рысев — Активные продажи 3.4.fb2"
    ).catalog_id == "rysev-active-sales"
    assert match_known_title("Ян Броди — Продающие рассылки.fb2").catalog_id == "brody-email"
    assert match_known_title("random-notes.txt") is None


def test_ingest_keeps_unmapped_file_and_stays_open_for_more_books(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "SPIN_Selling.txt").write_text("Need-payoff questions come last.\n", encoding="utf-8")
    (incoming / "later-purchase-notes.txt").write_text("owner will name this title later\n", encoding="utf-8")
    registry = tmp_path / "corpus-registry.json"
    status = ingest_sales_corpus(
        corpus_dir=tmp_path,
        registry_path=registry,
        manifest_path=tmp_path / "no-manifest.md",
        derived_dir=tmp_path / "jsonl",
        index_path=tmp_path / "index.json",
        cards_path=tmp_path / "cards.json",
    )
    assert status["ready_for_step2_training"] is True
    assert status["training_job_started"] is False
    assert "spin-selling" in status["mapped_known_titles"]
    assert "later-purchase-notes.txt" in status["unmapped_files"]
    assert "incoming" in status["next_owner_step"]
    assert "re-run ingest anytime" in status["next_owner_step"]
    assert status["sft_core_titles"] == ["spin-selling"]
    assert "later-purchase-notes.txt" in status["unmapped_files"]


def test_archive_titles_do_not_unlock_sft_rows() -> None:
    by_id = {title.catalog_id: title for title in KNOWN_TITLES}
    analyzer, generator = rows_for_title(by_id["crossing-the-chasm"])
    assert analyzer == []
    assert generator == []
    analyzer, generator = rows_for_title(by_id["nudge"])
    assert analyzer == []
    assert generator == []


def test_ingest_archive_only_is_not_ready_for_step2(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "Crossing_the_Chasm.txt").write_text(
        "Early adopters sit on one side of the chasm.\n",
        encoding="utf-8",
    )
    status = ingest_sales_corpus(
        corpus_dir=tmp_path,
        registry_path=tmp_path / "registry.json",
        manifest_path=tmp_path / "no-manifest.md",
        derived_dir=tmp_path / "jsonl",
        index_path=tmp_path / "index.json",
        cards_path=tmp_path / "cards.json",
    )
    assert status["mapped_known_titles"] == ["crossing-the-chasm"]
    assert status["sft_core_titles"] == []
    assert status["archive_mapped_titles"] == ["crossing-the-chasm"]
    assert status["ready_for_step2_training"] is False
    assert status["training_job_started"] is False
    analyzer_path = tmp_path / "jsonl" / "analyzer_from_corpus.jsonl"
    assert analyzer_path.read_text(encoding="utf-8").strip() == ""


def test_all_derived_rows_match_live_schemas() -> None:
    from src.companion_corpus.ingest import _validate_rows

    for title in KNOWN_TITLES:
        analyzer, generator = rows_for_title(title)
        _validate_rows(analyzer, generator)


def test_mapped_sales_titles_have_analyzer_and_generator_rows() -> None:
    required = (
        "spin-selling",
        "challenger-sale",
        "influence",
        "never-split-the-difference",
        "fanatical-prospecting",
        "sandler-rules",
        "getting-to-yes",
        "selling-to-big-companies",
        "agile-selling",
        "storybrand",
        "storybrand-2",
        "storybrand-funnel",
        "rysev-active-sales",
        "hbr-sales",
        "brody-email",
        "zaid-sales-bible",
        "hsieh-service",
    )
    by_id = {title.catalog_id: title for title in KNOWN_TITLES}
    assert set(required) == CORE_CATALOG_IDS
    for catalog_id in required:
        analyzer, generator = rows_for_title(by_id[catalog_id])
        assert analyzer, catalog_id
        assert generator, catalog_id
        assert len(analyzer) >= 5, catalog_id
        assert len(generator) >= 5, catalog_id


def test_ingest_txt_book_writes_derived_jsonl_and_stays_unapproved(
    tmp_path: Path,
) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    book = incoming / "SPIN_Selling.txt"
    book.write_text(
        "Chapter on situation questions.\n\nNeed-payoff questions come last.\n",
        encoding="utf-8",
    )
    registry = tmp_path / "corpus-registry.json"
    manifest = tmp_path / "manifest.md"
    manifest.write_text(
        "## Owner-deposited\n\n"
        "<!-- corpus-ingest:deposited:start -->\n"
        "old\n"
        "<!-- corpus-ingest:deposited:end -->\n\n"
        "## Ready for Step 2 training?\n\n"
        "<!-- corpus-ingest:ready:start -->\n"
        "**No.**\n"
        "<!-- corpus-ingest:ready:end -->\n",
        encoding="utf-8",
    )
    derived = tmp_path / "derived-jsonl"
    index = tmp_path / "deposit-index.json"
    cards = tmp_path / "cards.json"

    status = ingest_sales_corpus(
        corpus_dir=tmp_path,
        registry_path=registry,
        manifest_path=manifest,
        derived_dir=derived,
        index_path=index,
        cards_path=cards,
    )

    assert status["training_job_started"] is False
    assert status["cards_approved"] is False
    assert status["ready_for_step2_training"] is True
    assert status["mapped_known_titles"] == ["spin-selling"]
    assert (tmp_path / ".extracted").exists()
    sidecar = incoming / "SPIN_Selling.txt.licence.json"
    assert sidecar.exists()
    licence = json.loads(sidecar.read_text(encoding="utf-8"))
    assert licence["licence"] == "my-copy"

    analyzer_path = derived / "analyzer_from_corpus.jsonl"
    rows = [
        json.loads(line)
        for line in analyzer_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    for row in rows:
        target = SalesTurnAnalysisOutput.model_validate(row["target"])
        for signal in target.signals:
            assert signal.evidence in row["customer_message"]

    gen_rows = [
        json.loads(line)
        for line in (derived / "generator_from_corpus.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert gen_rows
    for row in gen_rows:
        output = SalesResponseOutput.model_validate(row["target"])
        assert check_move_matches_approved(output, SalesMove(row["approved_move"])) == []

    overlay = json.loads(cards.read_text(encoding="utf-8"))
    assert overlay[0]["status"] == "candidate"
    assert overlay[0]["version"] == 0

    extracted = list((tmp_path / ".extracted").glob("*.txt"))
    assert extracted
    pages = extract_pages(book)
    hits = locate_markers(pages, match_known_title(book.name).markers)
    assert hits

    manifest_text = manifest.read_text(encoding="utf-8")
    assert "SPIN_Selling.txt" in manifest_text
    assert "**Yes (corpus only" in manifest_text


def test_ingest_without_books_is_not_ready(tmp_path: Path) -> None:
    (tmp_path / "incoming").mkdir()
    registry = tmp_path / "corpus-registry.json"
    manifest = tmp_path / "manifest.md"
    manifest.write_text(
        "<!-- corpus-ingest:deposited:start -->\n"
        "<!-- corpus-ingest:deposited:end -->\n"
        "<!-- corpus-ingest:ready:start -->\n"
        "**No.**\n"
        "<!-- corpus-ingest:ready:end -->\n",
        encoding="utf-8",
    )
    status = ingest_sales_corpus(
        corpus_dir=tmp_path,
        registry_path=registry,
        manifest_path=manifest,
        derived_dir=tmp_path / "jsonl",
        index_path=tmp_path / "index.json",
        cards_path=tmp_path / "cards.json",
    )
    assert status["ready_for_step2_training"] is False
    assert status["deposited_files"] == 0
    assert status["training_job_started"] is False
    assert "incoming" in status["next_owner_step"]


def test_extract_fb2_strips_binary_and_chunks(tmp_path: Path) -> None:
    book = tmp_path / "sample.fb2"
    book.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <description><title-info><book-title>Sample</book-title></title-info></description>
  <body>
    <section><p>Situation questions come first.</p><p>Need-payoff questions come last.</p></section>
  </body>
  <binary id="cover.jpg">QQ==</binary>
</FictionBook>
""",
        encoding="utf-8",
    )
    pages = extract_pages(book)
    joined = " ".join(pages)
    assert "Situation questions" in joined
    assert "QQ==" not in joined
    assert "Sample" not in joined
