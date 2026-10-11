"""get_summary tool — returns expense summaries for a given period."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.db import operations as db
from app.models.tools import GetSummaryInput, GetSummaryOutput

logger = logging.getLogger(__name__)


def _get_period_bounds(period: str) -> tuple[datetime, datetime]:
    """Compute the start and end datetimes for a period.

    Returns (start_inclusive, end_exclusive) as timezone-aware datetimes.
    """
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return today_start, today_start + timedelta(days=1)
    elif period == "this_week":
        # Week starts on Monday
        monday = today_start - timedelta(days=today_start.weekday())
        return monday, monday + timedelta(weeks=1)
    elif period == "this_month":
        month_start = today_start.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        return month_start, month_end
    elif period == "last_month":
        this_month_start = today_start.replace(day=1)
        if this_month_start.month == 1:
            last_month_start = this_month_start.replace(
                year=this_month_start.year - 1, month=12
            )
        else:
            last_month_start = this_month_start.replace(
                month=this_month_start.month - 1
            )
        return last_month_start, this_month_start
    else:
        raise ValueError(f"Unknown period: {period}")


async def get_summary(
    user_id: UUID,
    args: dict[str, Any],
    **kwargs: Any,
) -> GetSummaryOutput:
    """Get an expense summary for the specified period."""
    inp = GetSummaryInput(**args)
    start, end = _get_period_bounds(inp.period)

    # Get overall total and count
    total_row = await db.get_total_by_period(user_id, start, end)
    total = Decimal(str(total_row["total"]))
    count = int(total_row["count"])

    # Get per-category breakdown
    category_rows = await db.get_category_totals(user_id, start, end)
    by_category = {
        row["category"]: Decimal(str(row["total"])) for row in category_rows
    }

    # Build human-readable message
    period_label = inp.period.replace("_", " ")
    msg_parts = [f"📊 Spending summary for {period_label}:"]
    msg_parts.append(f"💰 Total: ₹{total} ({count} expense{'s' if count != 1 else ''})")

    if by_category:
        msg_parts.append("\nBy category:")
        for cat, amt in by_category.items():
            msg_parts.append(f"  • {cat}: ₹{amt}")
    else:
        msg_parts.append("No expenses recorded for this period.")

    return GetSummaryOutput(
        period=inp.period,
        total=total,
        by_category=by_category,
        expense_count=count,
        message="\n".join(msg_parts),
    )
