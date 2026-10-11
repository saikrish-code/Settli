"""Database CRUD operations.

Thin async wrappers around SQL queries. Each function acquires a connection
from the pool, executes the query, and returns typed results.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from app.db import queries
from app.db.pool import get_pool

logger = logging.getLogger(__name__)


# ── Users ──────────────────────────────────────────────────────


async def upsert_user(phone: str, name: str | None = None) -> asyncpg.Record:
    """Create or update a user by phone number. Returns the user row."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(queries.UPSERT_USER, phone, name)
    logger.info("Upserted user: phone=%s", phone)
    return row  # type: ignore[return-value]


async def get_user_by_phone(phone: str) -> asyncpg.Record | None:
    """Look up a user by phone number."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(queries.GET_USER_BY_PHONE, phone)


# ── Contacts ───────────────────────────────────────────────────


async def upsert_contact(
    owner_id: UUID, name: str, phone: str
) -> asyncpg.Record:
    """Add or update a contact for a user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(queries.UPSERT_CONTACT, owner_id, name, phone)
    logger.info("Upserted contact: owner=%s, name=%s", owner_id, name)
    return row  # type: ignore[return-value]


async def get_contacts_by_owner(owner_id: UUID) -> list[asyncpg.Record]:
    """List all contacts for a user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(queries.GET_CONTACTS_BY_OWNER, owner_id)


async def get_contact_by_name(
    owner_id: UUID, name: str
) -> asyncpg.Record | None:
    """Look up a contact by name (case-insensitive)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(queries.GET_CONTACT_BY_NAME, owner_id, name)


# ── Expenses ───────────────────────────────────────────────────


async def insert_expense(
    user_id: UUID,
    amount: Decimal,
    category: str,
    description: str | None,
    split_with: list[str],
    split_amounts: list[Decimal],
    message_sid: str | None = None,
) -> asyncpg.Record:
    """Insert a new expense."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            queries.INSERT_EXPENSE,
            user_id,
            amount,
            category,
            description,
            split_with,
            split_amounts,
            message_sid,
        )
    logger.info(
        "Inserted expense: user=%s, amount=%s, category=%s", user_id, amount, category
    )
    return row  # type: ignore[return-value]


async def get_expenses_by_period(
    user_id: UUID, start: datetime, end: datetime
) -> list[asyncpg.Record]:
    """Get all expenses for a user within a time period."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(queries.GET_EXPENSES_BY_PERIOD, user_id, start, end)


async def get_category_totals(
    user_id: UUID, start: datetime, end: datetime
) -> list[asyncpg.Record]:
    """Get per-category spending totals for a period."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            queries.GET_CATEGORY_TOTALS_BY_PERIOD, user_id, start, end
        )


async def get_total_by_period(
    user_id: UUID, start: datetime, end: datetime
) -> asyncpg.Record:
    """Get total spending and count for a period."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(queries.GET_TOTAL_BY_PERIOD, user_id, start, end)
    return row  # type: ignore[return-value]


async def get_category_total_this_month(
    user_id: UUID, category: str
) -> Decimal:
    """Get total spending for a category this month."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            queries.GET_CATEGORY_TOTAL_THIS_MONTH, user_id, category
        )
    return Decimal(str(row["total"])) if row else Decimal("0")  # type: ignore[index]


# ── Budgets ────────────────────────────────────────────────────


async def upsert_budget(
    user_id: UUID, category: str, monthly_limit: Decimal
) -> asyncpg.Record:
    """Set or update a monthly budget for a category."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            queries.UPSERT_BUDGET, user_id, category, monthly_limit
        )
    logger.info("Upserted budget: user=%s, category=%s, limit=%s", user_id, category, monthly_limit)
    return row  # type: ignore[return-value]


async def get_budget(
    user_id: UUID, category: str
) -> asyncpg.Record | None:
    """Get the budget for a specific category."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(queries.GET_BUDGET, user_id, category)


# ── Reminders ──────────────────────────────────────────────────


async def insert_reminder(
    user_id: UUID, message: str, remind_at: datetime
) -> asyncpg.Record:
    """Create a new reminder."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(queries.INSERT_REMINDER, user_id, message, remind_at)
    logger.info("Inserted reminder: user=%s, at=%s", user_id, remind_at)
    return row  # type: ignore[return-value]


async def get_pending_reminders() -> list[asyncpg.Record]:
    """Get all reminders that are due and not yet sent."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(queries.GET_PENDING_REMINDERS)


async def mark_reminder_sent(reminder_id: UUID) -> None:
    """Mark a reminder as sent."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(queries.MARK_REMINDER_SENT, reminder_id)


# ── Audit Log ──────────────────────────────────────────────────


async def insert_audit_log(
    user_id: UUID | None,
    message_sid: str | None,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: dict[str, Any] | None,
    status: str = "success",
) -> asyncpg.Record:
    """Write an entry to the audit log."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            queries.INSERT_AUDIT_LOG,
            user_id,
            message_sid,
            tool_name,
            json.dumps(tool_input, default=str),
            json.dumps(tool_output, default=str) if tool_output else None,
            status,
        )
    logger.info("Audit log: tool=%s, status=%s, user=%s", tool_name, status, user_id)
    return row  # type: ignore[return-value]


# ── Idempotency ────────────────────────────────────────────────


async def try_insert_processed_message(
    message_sid: str, response_body: str
) -> bool:
    """Attempt to record a processed message. Returns True if inserted (new),
    False if already existed (duplicate)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            queries.INSERT_PROCESSED_MESSAGE, message_sid, response_body
        )
    # asyncpg returns "INSERT 0 1" for success, "INSERT 0 0" for conflict
    inserted = result.endswith("1")
    if not inserted:
        logger.warning("Duplicate message detected: %s", message_sid)
    return inserted


async def get_processed_message(message_sid: str) -> asyncpg.Record | None:
    """Get the cached response for a previously processed message."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(queries.GET_PROCESSED_MESSAGE, message_sid)
