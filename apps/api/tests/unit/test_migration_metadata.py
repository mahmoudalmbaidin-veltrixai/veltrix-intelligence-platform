"""Contracts for the complete ORM metadata graph consumed by Alembic."""

from vip_api.database import metadata as alembic_metadata


def test_notification_reads_is_registered_in_authoritative_metadata() -> None:
    registered_modules = {module.__name__ for module in alembic_metadata.MODEL_MODULES}
    table = alembic_metadata.target_metadata.tables["notification_reads"]

    assert "vip_api.home.models" in registered_modules
    assert table.key == "notification_reads"
    assert table is alembic_metadata.target_metadata.tables[table.key]
