"""log_expense tool — records an expense to the database.

Also checks for budget overruns and triggers split_bill if participants
are provided.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.db import operations as db
from app.models.tools import LogExpenseInput, LogExpenseOutput

logger = logging.getLogger(__name__)


async def log_expense(
    user_id: UUID,
    args: dict[str, Any],
    message_sid: str | None = None,
) -> LogExpenseOutput:
    """Validate args, insert expense, check budget, return result."""
    # Validate input through Pydantic
    inp = LogExpenseInput(**args)

    # Insert the expense
    row = await db.insert_expense(
        user_id=user_id,
        amount=inp.amount,
        category=inp.category,
        description=inp.description,
        split_with=inp.split_with,
        split_amounts=[],  # Will be filled by split_bill if needed
        message_sid=message_sid,
    )

    expense_id: UUID = row["id"]

    # Check budget
    budget_warning = await _check_budget(user_id, inp.category, inp.amount)

    # Build response
    msg = f"✅ Logged ₹{inp.amount} for {inp.description} ({inp.category})"
    if inp.split_with:
        names = ", ".join(inp.split_with)
        msg += f" — splitting with {names}"

    result = LogExpenseOutput(
        expense_id=expense_id,
        amount=inp.amount,
        category=inp.category,
        description=inp.description,
        message=msg,
        budget_warning=budget_warning,
    )

    logger.info("Logged expense: id=%s, amount=%s", expense_id, inp.amount)
    return result


async def _check_budget(
    user_id: UUID, category: str, new_amount: Decimal
) -> str | None:
    """Check if this expense pushes the user over their budget."""
    # Check category-specific budget
    budget_row = await db.get_budget(user_id, category)
    if budget_row is None:
        # Also check "overall" budget
        budget_row = await db.get_budget(user_id, "overall")

    if budget_row is None:
        return None

    limit = Decimal(str(budget_row["monthly_limit"]))
    current_total = await db.get_category_total_this_month(user_id, category)

    if current_total > limit:
        return (
            f"⚠️ Budget alert! You've spent ₹{current_total}/₹{limit} "
            f"on {category} this month."
        )
    elif current_total > limit * Decimal("0.8"):
        remaining = limit - current_total
        return (
            f"📊 Heads up: You've used {int(current_total / limit * 100)}% "
            f"of your {category} budget. ₹{remaining} remaining."
        )

    return None
