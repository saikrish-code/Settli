"""asyncpg connection pool lifecycle management.

The pool is created on app startup and closed on shutdown via FastAPI's
lifespan context manager.
"""

from __future__ import annotations

import logging

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level pool reference
_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]


async def create_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Create and cache the connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    logger.info("Creating asyncpg connection pool for %s", settings.database_url)
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("Connection pool created successfully")
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Connection pool closed")


def get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Get the current connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. "
            "Did you forget to call create_pool() in the app lifespan?"
        )
    return _pool
