"""set_reminder tool — creates a reminder for a future date/time."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.db import operations as db
from app.models.tools import SetReminderInput, SetReminderOutput

logger = logging.getLogger(__name__)


async def set_reminder(
    user_id: UUID,
    args: dict[str, Any],
    **kwargs: Any,
) -> SetReminderOutput:
    """Validate args, insert reminder, return confirmation."""
    inp = SetReminderInput(**args)

    row = await db.insert_reminder(
        user_id=user_id,
        message=inp.message,
        remind_at=inp.remind_at,
    )

    reminder_id = row["id"]
    formatted_time = inp.remind_at.strftime("%B %d, %Y at %I:%M %p")

    confirmation = (
        f"⏰ Reminder set!\n"
        f"📝 {inp.message}\n"
        f"🗓️ {formatted_time}"
    )

    logger.info("Set reminder: id=%s, at=%s", reminder_id, inp.remind_at)

    return SetReminderOutput(
        reminder_id=reminder_id,
        message=inp.message,
        remind_at=inp.remind_at,
        confirmation=confirmation,
    )
