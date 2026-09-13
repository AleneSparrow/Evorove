"""Owner-uploaded marketing packet used as approved facts for the sales engine."""

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
import json

from .models import _require_aware, _require_text

ASSET_KINDS = frozenset({"notes", "offer", "media"})
SNAPSHOT_SCHEMA = "owner_materials.v1"
_BINARY_CUE = "binary media is stored as a label only"


@dataclass(frozen=True, slots=True)
class MarketingAsset:
    asset_id: str
    business_id: str
    kind: str
    title: str
    body_text: str
    filename: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.asset_id, "asset_id")
        _require_text(self.business_id, "business_id")
        if self.kind not in ASSET_KINDS:
            raise ValueError(f"unknown marketing asset kind: {self.kind!r}")
        _require_text(self.title, "title")
        _require_aware(self.created_at, "created_at")
        if self.filename is not None:
            _require_text(self.filename, "filename")


@dataclass(frozen=True, slots=True)
class MarketingGuidance:
    business_id: str
    revision: int
    snapshot_text: str
    activated_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.business_id, "business_id")
        if self.revision < 1:
            raise ValueError("marketing guidance revision must be >= 1")
        _require_aware(self.activated_at, "activated_at")


@dataclass(frozen=True, slots=True)
class SnapshotItem:
    asset_id: str
    kind: str
    title: str
    body_text: str
    filename: str | None = None

    def usable_fact_text(self) -> str | None:
        body = self.body_text.strip()
        if not body or _BINARY_CUE in body.casefold():
            return None
        title = self.title.strip()
        text = f"{title}: {body}" if title else body
        return text[:1_500]


def encode_snapshot(assets: tuple[MarketingAsset, ...]) -> str:
    items = [
        {
            "asset_id": asset.asset_id,
            "kind": asset.kind,
            "title": asset.title,
            "body_text": asset.body_text,
            "filename": asset.filename,
        }
        for asset in sorted(assets, key=lambda item: item.created_at)
    ]
    return json.dumps({"schema": SNAPSHOT_SCHEMA, "items": items}, ensure_ascii=True, sort_keys=True)


def decode_snapshot(snapshot_text: str) -> tuple[SnapshotItem, ...]:
    raw = (snapshot_text or "").strip()
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return (SnapshotItem("legacy", "notes", "Owner packet", raw, None),)
    if not isinstance(payload, Mapping) or payload.get("schema") != SNAPSHOT_SCHEMA:
        return (SnapshotItem("legacy", "notes", "Owner packet", raw, None),)
    parsed: list[SnapshotItem] = []
    items = payload.get("items")
    if not isinstance(items, list):
        return ()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        asset_id = item.get("asset_id")
        kind = item.get("kind")
        title = item.get("title")
        body = item.get("body_text")
        filename = item.get("filename")
        if not isinstance(asset_id, str) or not asset_id.strip():
            continue
        if kind not in ASSET_KINDS:
            continue
        if not isinstance(title, str) or not isinstance(body, str):
            continue
        parsed.append(
            SnapshotItem(
                asset_id=asset_id.strip(),
                kind=str(kind),
                title=title,
                body_text=body,
                filename=filename.strip() if isinstance(filename, str) and filename.strip() else None,
            )
        )
    return tuple(parsed)


def snapshot_plain_text(snapshot_text: str) -> str:
    items = decode_snapshot(snapshot_text)
    if not items:
        return ""
    parts: list[str] = []
    for item in items:
        header = f"[{item.kind.upper()}] {item.title}"
        if item.filename:
            header += f" ({item.filename})"
        parts.append(f"{header}\n{item.body_text}")
    return "\n\n".join(parts)
