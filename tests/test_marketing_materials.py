"""C2-3: owner materials are facts. Presentation picks one activated item."""

from datetime import datetime, timezone
from pathlib import Path

from src.domain.marketing_materials import SnapshotItem, encode_snapshot
from src.domain.sales import CustomerSalesProfile, SalesStage
from src.domain.tenancy import Business
from src.engine.owner_material_pick import pick_activated_owner_material, pick_relevant_snapshot_item
from src.engine.sales_live_turn import combined_business_facts
from src.persistence.marketing_materials_service import MarketingMaterialsService
from src.persistence.owner_materials import merge_active_owner_materials
from src.persistence.sqlalchemy_models import Base
from src.persistence.sqlalchemy_uow import SQLAlchemyUnitOfWork, create_database_engine

NOW = datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc)
BUSINESS_ID = "studio-1"


def _factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'materials.db'}")
    Base.metadata.create_all(engine)
    return SQLAlchemyUnitOfWork.factory_for_engine(engine), engine


def _seed_business(factory) -> None:
    with factory() as unit_of_work:
        unit_of_work.businesses.add(
            Business(BUSINESS_ID, BUSINESS_ID, NOW, NOW, plan="starter", subscription_status="active")
        )
        unit_of_work.commit()


def test_pick_returns_one_matching_offer() -> None:
    items = (
        SnapshotItem("a", "notes", "About us", "We opened in 2019.", None),
        SnapshotItem("b", "offer", "Chicago loop package", "Same-week visit for Loop offices.", None),
        SnapshotItem("c", "offer", "Residential tune-up", "Home AC tune-up in the suburbs.", None),
    )
    chosen = pick_relevant_snapshot_item(
        items,
        problem="office AC died in the Loop",
        outcome="same week visit",
        goal=None,
    )
    assert chosen is not None
    assert chosen.asset_id == "b"


def test_pick_skips_binary_labels() -> None:
    items = (
        SnapshotItem(
            "pic",
            "media",
            "storefront.jpg",
            "Uploaded file: storefront.jpg. Binary media is stored as a label only; describe what it shows.",
            "storefront.jpg",
        ),
        SnapshotItem("note", "notes", "Hours", "Open Tuesday through Saturday.", None),
    )
    chosen = pick_relevant_snapshot_item(items, problem=None, outcome=None, goal=None)
    assert chosen is not None
    assert chosen.asset_id == "note"


def test_drafts_are_ignored_until_refresh(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        _seed_business(factory)
        service = MarketingMaterialsService(factory)
        service.add_text_asset(
            BUSINESS_ID,
            kind="offer",
            title="Autumn package",
            body_text="90-minute consult, no same-day booking promise.",
        )
        profile = CustomerSalesProfile(BUSINESS_ID, "case-1", stage=SalesStage.NEEDS_CONFIRMED)
        with factory() as unit_of_work:
            merged = merge_active_owner_materials(
                unit_of_work,
                BUSINESS_ID,
                {"business": {"id": BUSINESS_ID, "description": "A studio."}},
            )
            picked = pick_activated_owner_material(unit_of_work, BUSINESS_ID, profile)
        assert merged["business"]["description"] == "A studio."
        assert picked is None

        service.activate(BUSINESS_ID)
        with factory() as unit_of_work:
            merged = merge_active_owner_materials(
                unit_of_work,
                BUSINESS_ID,
                {"business": {"id": BUSINESS_ID, "description": "A studio."}},
            )
            picked = pick_activated_owner_material(unit_of_work, BUSINESS_ID, profile)
        assert "Autumn package" not in merged["business"]["description"]
        assert picked is not None
        fact_id, text = picked
        assert fact_id.startswith("owner.material.")
        assert "90-minute consult" in text
        facts = combined_business_facts(
            merged, None, profile, extra=(picked,),
        )
        material_facts = [item for item in facts if item[0].startswith("owner.material.")]
        assert len(material_facts) == 1
    finally:
        engine.dispose()


def test_new_draft_does_not_replace_the_live_pick(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        _seed_business(factory)
        service = MarketingMaterialsService(factory)
        service.add_text_asset(BUSINESS_ID, kind="offer", title="Live offer", body_text="Named consult hour.")
        service.activate(BUSINESS_ID)
        service.add_text_asset(BUSINESS_ID, kind="offer", title="Draft offer", body_text="Secret unpublished discount.")
        profile = CustomerSalesProfile(
            BUSINESS_ID,
            "case-1",
            stage=SalesStage.NEEDS_CONFIRMED,
            current_problem="need a consult hour",
        )
        with factory() as unit_of_work:
            picked = pick_activated_owner_material(unit_of_work, BUSINESS_ID, profile)
        assert picked is not None
        assert "Named consult hour" in picked[1]
        assert "unpublished" not in picked[1]
    finally:
        engine.dispose()


def test_text_file_becomes_a_fact_after_refresh(tmp_path) -> None:
    factory, engine = _factory(tmp_path)
    try:
        _seed_business(factory)
        service = MarketingMaterialsService(factory)
        service.add_file_asset(
            BUSINESS_ID,
            filename="brief.txt",
            content=b"We serve Chicago loop offices.",
        )
        service.activate(BUSINESS_ID)
        with factory() as unit_of_work:
            picked = pick_activated_owner_material(unit_of_work, BUSINESS_ID, None)
        assert picked is not None
        assert "Chicago loop offices" in picked[1]
    finally:
        engine.dispose()


def test_encode_snapshot_round_trips_one_library() -> None:
    from src.domain.marketing_materials import MarketingAsset, decode_snapshot

    assets = (
        MarketingAsset("id-1", BUSINESS_ID, "offer", "Rate card", "$120 consult", None, NOW),
    )
    items = decode_snapshot(encode_snapshot(assets))
    assert len(items) == 1
    assert items[0].title == "Rate card"
