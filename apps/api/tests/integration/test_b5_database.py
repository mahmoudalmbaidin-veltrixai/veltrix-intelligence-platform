"""B5 migration presence and PostgreSQL read-only execution integration tests."""

import pytest
from sqlalchemy import text

from vip_api.core.config import Settings
from vip_api.database.session import Database


@pytest.mark.integration
@pytest.mark.asyncio
async def test_b5_tables_and_read_only_transaction_are_operational(settings: Settings) -> None:
    database = Database(settings)
    try:
        async with database.session_factory() as db:
            names = set(
                (
                    await db.scalars(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema='public'"
                        )
                    )
                ).all()
            )
            assert {
                "datasets",
                "dataset_fields",
                "dataset_quality_rules",
                "dataset_quality_results",
                "dataset_lineage_edges",
                "semantic_models",
                "semantic_dimensions",
                "semantic_measures",
                "semantic_metrics",
                "semantic_kpis",
                "glossary_domains",
                "glossary_terms",
            } <= names
            await db.execute(text("SET TRANSACTION READ ONLY"))
            assert await db.scalar(text("SELECT 1")) == 1
            with pytest.raises(Exception):  # noqa: B017
                await db.execute(text("CREATE TEMP TABLE b5_write_probe(id integer)"))
            await db.rollback()
    finally:
        await database.dispose()
