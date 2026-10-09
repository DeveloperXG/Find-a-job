import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

API_DIR = Path(__file__).resolve().parents[1]


def alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Run Alembic against the test database (subprocess: env.py owns its own event loop)."""
    env = {**os.environ, "DATABASE_URL": get_settings().test_database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="session")
def migrated_db() -> str:
    """Bring `jt_test` to head through the real migrations (so tests exercise them too)."""
    result = alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr
    return get_settings().test_database_url


@pytest.fixture
async def db_session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """Session inside an outer transaction that is always rolled back.

    `create_savepoint` lets tests trigger and recover from IntegrityError without
    ending the outer transaction.
    """
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
