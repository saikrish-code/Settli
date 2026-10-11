"""set_budget tool — sets a monthly spending budget per category."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.db import operations as db
from app.models.tools import SetBudgetInput, SetBudgetOutput

logger = logging.getLogger(__name__)


async def set_budget(
    user_id: UUID,
    args: dict[str, Any],
    **kwargs: Any,
) -> SetBudgetOutput:
    """Validate args, upsert budget, return confirmation."""
    inp = SetBudgetInput(**args)

    row = await db.upsert_budget(
        user_id=user_id,
        category=inp.category,
        monthly_limit=inp.monthly_limit,
    )

    budget_id = row["id"]

    confirmation = (
        f"✅ Budget set!\n"
        f"📂 Category: {inp.category}\n"
        f"💰 Monthly limit: ₹{inp.monthly_limit}"
    )

    logger.info(
        "Set budget: id=%s, category=%s, limit=%s",
        budget_id,
        inp.category,
        inp.monthly_limit,
    )

    return SetBudgetOutput(
        budget_id=budget_id,
        category=inp.category,
        monthly_limit=inp.monthly_limit,
        confirmation=confirmation,
    )
