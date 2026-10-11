"""Shared test fixtures.

Provides mocked DB, mocked Twilio client, and the FastAPI test client.
All tests run without a real database or external API calls.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient


# ── Fake DB Records ────────────────────────────────────────────


def make_user_record(
    user_id: UUID | None = None,
    phone: str = "whatsapp:+919876543210",
    name: str | None = "TestUser",
) -> dict[str, Any]:
    """Create a fake user record matching asyncpg.Record interface."""
    return {
        "id": user_id or uuid4(),
        "phone": phone,
        "name": name,
        "created_at": "2024-01-01T00:00:00+00:00",
    }


def make_expense_record(
    expense_id: UUID | None = None,
    user_id: UUID | None = None,
    amount: float = 250.0,
    category: str = "food",
    description: str = "chai",
) -> dict[str, Any]:
    """Create a fake expense record."""
    return {
        "id": expense_id or uuid4(),
        "user_id": user_id or uuid4(),
        "amount": Decimal(str(amount)),
        "category": category,
        "description": description,
        "split_with": [],
        "split_amounts": [],
        "message_sid": None,
        "created_at": "2024-01-01T00:00:00+00:00",
    }


def make_contact_record(
    name: str = "Raj",
    phone: str = "+919876500001",
    owner_id: UUID | None = None,
) -> dict[str, Any]:
    """Create a fake contact record."""
    return {
        "id": uuid4(),
        "owner_id": owner_id or uuid4(),
        "name": name,
        "phone": phone,
        "created_at": "2024-01-01T00:00:00+00:00",
    }


def make_budget_record(
    category: str = "food",
    monthly_limit: float = 3000.0,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    """Create a fake budget record."""
    return {
        "id": uuid4(),
        "user_id": user_id or uuid4(),
        "category": category,
        "monthly_limit": Decimal(str(monthly_limit)),
        "created_at": "2024-01-01T00:00:00+00:00",
    }


def make_reminder_record(
    message: str = "Pay rent",
    user_id: UUID | None = None,
) -> dict[str, Any]:
    """Create a fake reminder record."""
    return {
        "id": uuid4(),
        "user_id": user_id or uuid4(),
        "message": message,
        "remind_at": "2024-02-05T09:00:00+00:00",
        "is_sent": False,
        "created_at": "2024-01-01T00:00:00+00:00",
    }


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def user_id() -> UUID:
    """A consistent user UUID for tests."""
    return uuid4()


@pytest.fixture
def mock_db(user_id: UUID):
    """Mock all database operations.

    Returns a dict of all mocked functions for easy assertion.
    """
    user_record = make_user_record(user_id=user_id)
    expense_record = make_expense_record(user_id=user_id)
    budget_record = make_budget_record(user_id=user_id)
    reminder_record = make_reminder_record(user_id=user_id)

    mocks = {
        "upsert_user": AsyncMock(return_value=user_record),
        "get_user_by_phone": AsyncMock(return_value=user_record),
        "upsert_contact": AsyncMock(return_value=make_contact_record(owner_id=user_id)),
        "get_contacts_by_owner": AsyncMock(return_value=[]),
        "get_contact_by_name": AsyncMock(return_value=None),
        "insert_expense": AsyncMock(return_value=expense_record),
        "get_expenses_by_period": AsyncMock(return_value=[]),
        "get_category_totals": AsyncMock(return_value=[]),
        "get_total_by_period": AsyncMock(
            return_value={"total": Decimal("0"), "count": 0}
        ),
        "get_category_total_this_month": AsyncMock(return_value=Decimal("0")),
        "upsert_budget": AsyncMock(return_value=budget_record),
        "get_budget": AsyncMock(return_value=None),
        "insert_reminder": AsyncMock(return_value=reminder_record),
        "get_pending_reminders": AsyncMock(return_value=[]),
        "mark_reminder_sent": AsyncMock(),
        "insert_audit_log": AsyncMock(
            return_value={"id": uuid4(), "tool_name": "test", "created_at": "2024-01-01T00:00:00+00:00"}
        ),
        "try_insert_processed_message": AsyncMock(return_value=True),
        "get_processed_message": AsyncMock(return_value=None),
    }

    patches = []
    for name, mock in mocks.items():
        p = patch(f"app.db.operations.{name}", mock)
        patches.append(p)
        p.start()

    yield mocks

    for p in patches:
        p.stop()


@pytest.fixture
def mock_twilio():
    """Mock the Twilio send_whatsapp_message function."""
    with patch(
        "app.services.twilio_client.send_whatsapp_message",
        new_callable=AsyncMock,
        return_value="SM_mock_sid",
    ) as mock:
        # Also patch the import in split_bill module
        with patch(
            "app.tools.split_bill.send_whatsapp_message",
            new_callable=AsyncMock,
            return_value="SM_mock_sid",
        ) as mock2:
            yield mock2


@pytest.fixture
def test_client(mock_db, mock_twilio):
    """FastAPI test client with all external dependencies mocked."""
    # Patch the pool to avoid real DB connections
    with patch("app.db.pool.create_pool", new_callable=AsyncMock):
        with patch("app.db.pool.close_pool", new_callable=AsyncMock):
            with patch("app.db.pool.get_pool", return_value=MagicMock()):
                # Also patch DB operations used directly in main.py
                with patch("app.main.db", mock_db):
                    from app.main import app
                    client = TestClient(app)
                    yield client
