from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.models import Base
from tests.conftest import alembic

EXPECTED_TABLES = {
    "companies",
    "job_sources",
    "jobs",
    "job_matches",
    "profile",
    "resumes",
    "applications",
    "application_events",
    "notifications",
    "workflow_runs",
    "llm_calls",
}


async def table_names(url: str) -> set[str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()
    return names - {"alembic_version"}


def test_models_cover_every_table_in_the_schema() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


async def test_downgrade_base_then_upgrade_head(migrated_db: str) -> None:
    assert await table_names(migrated_db) == EXPECTED_TABLES

    down = alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr
    assert await table_names(migrated_db) == set()

    up = alembic("upgrade", "head")  # leave the schema in place for the other tests
    assert up.returncode == 0, up.stderr
    assert await table_names(migrated_db) == EXPECTED_TABLES


def test_migration_matches_models(migrated_db: str) -> None:
    """`alembic check` fails if the models drift from 0001 (i.e. someone forgot a migration)."""
    result = alembic("check")
    assert result.returncode == 0, result.stdout + result.stderr
