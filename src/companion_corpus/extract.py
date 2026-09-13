"""Extract page text from owner-deposited files. Output stays under private/."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class UnsupportedCorpusFile(ValueError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_pages(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    head = path.read_bytes()[:8]
    if head.startswith(b"7z"):
        return _extract_sevenzip_ebook(path)
    if suffix in {".txt", ".md"}:
        return _chunk_plain(path.read_text(encoding="utf-8", errors="replace"))
    if suffix in {".html", ".htm"}:
        return _chunk_plain(_strip_tags(path.read_text(encoding="utf-8", errors="replace")))
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".epub":
        return _extract_epub(path)
    if suffix == ".fb2":
        return _extract_fb2(path)
    if suffix == ".docx":
        return _extract_docx(path)
    raise UnsupportedCorpusFile(f"unsupported corpus suffix: {suffix}")


def write_extracted_copy(pages: list[str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n\n\f\n\n".join(pages), encoding="utf-8")


def locate_markers(pages: list[str], markers: tuple[str, ...]) -> dict[str, int]:
    hits: dict[str, int] = {}
    for index, page in enumerate(pages, start=1):
        lowered = page.casefold()
        for marker in markers:
            key = marker.casefold()
            if key not in hits and key in lowered:
                hits[marker] = index
    return hits


def _chunk_plain(text: str, size: int = 1800) -> list[str]:
    compact = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not compact:
        return []
    if "\f" in compact:
        parts = [chunk.strip() for chunk in compact.split("\f") if chunk.strip()]
        if len(parts) > 1:
            return parts
        compact = parts[0] if parts else compact
    return [compact[i : i + size] for i in range(0, len(compact), size)]


def _strip_tags(html: str) -> str:
    no_script = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"(?s)<[^>]+>", " ", no_script)


def _extract_pdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise UnsupportedCorpusFile(
            "PDF ingest needs pypdf. Install it in this environment, or drop a .txt "
            "export next to the PDF with the same stem."
        ) from exc
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append((page.extract_text() or "").strip())
    return pages


def _decode_xml_bytes(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    head = raw[:240].decode("ascii", errors="replace")
    match = re.search(r"encoding=['\"]([^'\"]+)['\"]", head, re.I)
    encoding = match.group(1) if match else "utf-8"
    try:
        return raw.decode(encoding)
    except LookupError:
        return raw.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _extract_fb2(path: Path) -> list[str]:
    text = _decode_xml_bytes(path.read_bytes())
    text = re.sub(r"(?is)<binary[^>]*>.*?</binary>", " ", text)
    text = re.sub(r"(?is)<description[^>]*>.*?</description>", " ", text, count=1)
    pages = _chunk_plain(_strip_tags(text))
    if not pages:
        raise UnsupportedCorpusFile(f"FB2 had no extractable text: {path.name}")
    return pages


def _pages_from_markup_files(files: list[Path]) -> list[str]:
    pages: list[str] = []
    for path in sorted(files):
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = _strip_tags(raw).strip()
        if text:
            pages.append(re.sub(r"\s+", " ", text))
    if not pages:
        raise UnsupportedCorpusFile("archive had no extractable HTML")
    return pages


def _extract_sevenzip_ebook(path: Path) -> list[str]:
    try:
        import py7zr
    except ImportError as exc:
        raise UnsupportedCorpusFile(
            "This file is a 7z archive named like an EPUB. Install py7zr, or drop a "
            "plain .fb2 / .epub / .txt export."
        ) from exc
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        with py7zr.SevenZipFile(path, mode="r") as archive:
            archive.extractall(path=tmp)
        markup = [
            item
            for item in Path(tmp).rglob("*")
            if item.is_file() and item.suffix.lower() in {".xhtml", ".html", ".htm"}
        ]
        return _pages_from_markup_files(markup)


def _extract_epub(path: Path) -> list[str]:
    pages: list[str] = []
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise UnsupportedCorpusFile(
            f"{path.name} is not a ZIP EPUB (often a 7z export). Re-export as FB2 or real EPUB."
        ) from exc
    with archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".xhtml", ".html", ".htm", ".xml"))
        ]
        for name in sorted(names):
            raw = archive.read(name).decode("utf-8", errors="replace")
            text = _strip_tags(raw).strip()
            if text:
                pages.append(re.sub(r"\s+", " ", text))
    if not pages:
        raise UnsupportedCorpusFile(f"EPUB had no extractable text: {path.name}")
    return pages


def _extract_docx(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    chunks: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        line = "".join(texts).strip()
        if line:
            chunks.append(line)
    return _chunk_plain("\n".join(chunks))
