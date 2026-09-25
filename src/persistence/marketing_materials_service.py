"""Owner marketing packet: notes, offer, files. Refresh publishes them to the engine."""

from uuid import uuid4

from src.domain.marketing_materials import ASSET_KINDS, MarketingAsset, MarketingGuidance, encode_snapshot
from src.domain.models import utc_now
from src.persistence.repositories import UnitOfWorkFactory

MAX_ASSETS = 40
MAX_BODY = 20_000
MAX_FILE_BYTES = 8_000_000
TEXT_SUFFIXES = (".txt", ".md", ".csv", ".json", ".html")
PDF_SUFFIXES = (".pdf",)


class MarketingMaterialsError(ValueError):
    pass


class MarketingMaterialsService:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._factory = unit_of_work_factory

    def list_packet(self, business_id: str) -> tuple[tuple[MarketingAsset, ...], MarketingGuidance | None]:
        with self._factory() as unit_of_work:
            return unit_of_work.marketing_materials.list_assets(business_id), unit_of_work.marketing_materials.get_guidance(
                business_id
            )

    def add_text_asset(self, business_id: str, *, kind: str, title: str, body_text: str) -> MarketingAsset:
        return self._add(
            business_id,
            kind=kind,
            title=title,
            body_text=body_text,
            filename=None,
        )

    def add_file_asset(self, business_id: str, *, filename: str, content: bytes) -> MarketingAsset:
        safe_name = filename.replace("\\", "/").split("/")[-1].strip()
        if not safe_name or safe_name in {".", ".."}:
            raise MarketingMaterialsError("file name is required")
        if len(content) > MAX_FILE_BYTES:
            raise MarketingMaterialsError("file is too large (8 MB max)")
        body = _file_body(safe_name, content)
        return self._add(
            business_id,
            kind="media",
            title=safe_name,
            body_text=body,
            filename=safe_name,
        )

    def activate(self, business_id: str) -> MarketingGuidance:
        with self._factory() as unit_of_work:
            assets = unit_of_work.marketing_materials.list_assets(business_id)
            snapshot = encode_snapshot(assets)
            current = unit_of_work.marketing_materials.get_guidance(business_id)
            revision = 1 if current is None else current.revision + 1
            guidance = MarketingGuidance(
                business_id=business_id,
                revision=revision,
                snapshot_text=snapshot,
                activated_at=utc_now(),
            )
            unit_of_work.marketing_materials.save_guidance(guidance)
            unit_of_work.commit()
            return guidance

    def _add(
        self,
        business_id: str,
        *,
        kind: str,
        title: str,
        body_text: str,
        filename: str | None,
    ) -> MarketingAsset:
        kind = kind.strip().casefold()
        if kind not in ASSET_KINDS:
            raise MarketingMaterialsError("kind must be notes, offer, or media")
        clean_title = title.strip()
        if not clean_title:
            raise MarketingMaterialsError("title is required")
        if len(clean_title) > 200:
            raise MarketingMaterialsError("title is too long")
        clean_body = body_text.strip()
        if not clean_body:
            raise MarketingMaterialsError("body is required")
        if len(clean_body) > MAX_BODY:
            raise MarketingMaterialsError("body is too long")
        with self._factory() as unit_of_work:
            if unit_of_work.marketing_materials.count_assets(business_id) >= MAX_ASSETS:
                raise MarketingMaterialsError("this business already has 40 materials")
            asset = MarketingAsset(
                asset_id=str(uuid4()),
                business_id=business_id,
                kind=kind,
                title=clean_title,
                body_text=clean_body,
                filename=filename,
                created_at=utc_now(),
            )
            unit_of_work.marketing_materials.add_asset(asset)
            unit_of_work.commit()
            return asset


def _file_body(filename: str, content: bytes) -> str:
    lower = filename.casefold()
    if lower.endswith(TEXT_SUFFIXES):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MarketingMaterialsError("text files must be UTF-8") from exc
        return text.strip() or f"Uploaded file: {filename}"
    if lower.endswith(PDF_SUFFIXES):
        extracted = _pdf_text(content)
        if extracted:
            return extracted
        return (
            f"Uploaded file: {filename}. PDF text could not be read; "
            "describe the price or offer in notes if the engine should use it as a fact."
        )
    return (
        f"Uploaded file: {filename}. Binary media is stored as a label only; "
        "describe what it shows in notes if the engine should use it as a fact."
    )


def _pdf_text(content: bytes) -> str:
    try:
        from io import BytesIO

        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        for page in reader.pages[:20]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        return ""


def build_snapshot(assets: tuple[MarketingAsset, ...]) -> str:
    return encode_snapshot(assets)
