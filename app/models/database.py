"""Pydantic models representing database rows.

These are NOT ORM models — we use raw asyncpg. These models are used to
type-annotate query results and provide a clean data layer.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class UserRow(BaseModel):
    """A row from the users table."""

    id: UUID
    phone: str
    name: str | None = None
    created_at: datetime


class ContactRow(BaseModel):
    """A row from the contacts table."""

    id: UUID
    owner_id: UUID
    name: str
    phone: str
    created_at: datetime


class ExpenseRow(BaseModel):
    """A row from the expenses table."""

    id: UUID
    user_id: UUID
    amount: Decimal
    category: str
    description: str | None = None
    split_with: list[str] = []
    split_amounts: list[Decimal] = []
    message_sid: str | None = None
    created_at: datetime


class BudgetRow(BaseModel):
    """A row from the budgets table."""

    id: UUID
    user_id: UUID
    category: str
    monthly_limit: Decimal
    created_at: datetime


class ReminderRow(BaseModel):
    """A row from the reminders table."""

    id: UUID
    user_id: UUID
    message: str
    remind_at: datetime
    is_sent: bool
    created_at: datetime


class AuditLogRow(BaseModel):
    """A row from the audit_log table."""

    id: UUID
    user_id: UUID | None = None
    message_sid: str | None = None
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: dict[str, Any] | None = None
    status: str
    created_at: datetime
