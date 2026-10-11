"""Pydantic models for tool inputs and outputs.

Each tool has a strictly-typed input model. The LLM's arguments are validated
against these before execution — if validation fails, the agent asks a
clarifying question instead of crashing.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# ── Tool Inputs ────────────────────────────────────────────────


class LogExpenseInput(BaseModel):
    """Input for the log_expense tool."""

    amount: Decimal = Field(..., gt=0, description="Expense amount (must be positive)")
    category: str = Field(default="general", description="Expense category")
    description: str = Field(..., min_length=1, description="What the expense was for")
    split_with: list[str] = Field(
        default_factory=list,
        description="Names of people to split with (empty = no split)",
    )

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: str) -> str:
        return v.strip()


class SplitBillInput(BaseModel):
    """Input for the split_bill tool."""

    expense_id: UUID = Field(..., description="ID of the expense to split")
    participants: list[str] = Field(
        ..., min_length=1, description="Names of people to split with"
    )
    total: Decimal = Field(..., gt=0, description="Total amount to split")


class GetSummaryInput(BaseModel):
    """Input for the get_summary tool."""

    period: str = Field(
        default="this_month",
        description="Time period: today, this_week, this_month, last_month",
    )
    category: str | None = Field(
        default=None, description="Filter by category (optional)"
    )

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        allowed = {"today", "this_week", "this_month", "last_month"}
        if v not in allowed:
            raise ValueError(f"period must be one of {allowed}")
        return v


class SetReminderInput(BaseModel):
    """Input for the set_reminder tool."""

    message: str = Field(..., min_length=1, description="Reminder message")
    remind_at: datetime = Field(..., description="When to send the reminder (ISO8601)")


class SetBudgetInput(BaseModel):
    """Input for the set_budget tool."""

    category: str = Field(default="overall", description="Budget category")
    monthly_limit: Decimal = Field(..., gt=0, description="Monthly spending limit")

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        return v.strip().lower()


# ── Tool Outputs ───────────────────────────────────────────────


class LogExpenseOutput(BaseModel):
    """Result of logging an expense."""

    expense_id: UUID
    amount: Decimal
    category: str
    description: str
    message: str
    budget_warning: str | None = None


class SplitBillOutput(BaseModel):
    """Result of splitting a bill."""

    expense_id: UUID
    total: Decimal
    shares: list[ShareDetail]
    message: str


class ShareDetail(BaseModel):
    """One participant's share in a split."""

    name: str
    phone: str | None = None
    amount: Decimal
    notified: bool = False


# Rebuild SplitBillOutput now that ShareDetail is defined
SplitBillOutput.model_rebuild()


class GetSummaryOutput(BaseModel):
    """Result of getting an expense summary."""

    period: str
    total: Decimal
    by_category: dict[str, Decimal]
    expense_count: int
    message: str


class SetReminderOutput(BaseModel):
    """Result of setting a reminder."""

    reminder_id: UUID
    message: str
    remind_at: datetime
    confirmation: str


class SetBudgetOutput(BaseModel):
    """Result of setting a budget."""

    budget_id: UUID
    category: str
    monthly_limit: Decimal
    confirmation: str
