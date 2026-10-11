"""split_bill tool — the key "agentic" behavior.

One user message triggers:
1. Contact lookup for each participant
2. Per-person share calculation (penny-perfect)
3. Outbound WhatsApp notification to each participant
4. Audit logging of each outbound message

This is the autonomous multi-step action that makes Settli an agent,
not just a chatbot.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.db import operations as db
from app.models.tools import ShareDetail, SplitBillOutput
from app.services.twilio_client import send_whatsapp_message
from app.tools.split_math import calculate_split

logger = logging.getLogger(__name__)


async def split_bill(
    user_id: UUID,
    args: dict[str, Any],
    message_sid: str | None = None,
    user_phone: str | None = None,
    user_name: str | None = None,
) -> SplitBillOutput:
    """Look up contacts, calculate shares, notify each participant."""
    participants: list[str] = args.get("participants", [])
    total = Decimal(str(args["total"]))
    expense_id = UUID(str(args["expense_id"]))

    # Total people = participants + the original user
    num_people = len(participants) + 1
    shares = calculate_split(total, num_people)

    # The user's own share is the first one
    user_share = shares[0]
    participant_shares = shares[1:]

    # Look up contacts and send notifications
    share_details: list[ShareDetail] = []

    # Add the user's own share
    share_details.append(
        ShareDetail(
            name=user_name or "You",
            phone=user_phone,
            amount=user_share,
            notified=False,  # We don't notify the user about their own share here
        )
    )

    # Look up and notify each participant concurrently
    notification_tasks = []
    for i, name in enumerate(participants):
        participant_amount = participant_shares[i]

        # Look up contact
        contact = await db.get_contact_by_name(user_id, name)

        if contact is not None:
            phone = contact["phone"]
            share_details.append(
                ShareDetail(
                    name=name,
                    phone=phone,
                    amount=participant_amount,
                    notified=False,  # Will be set to True after sending
                )
            )

            # Queue notification
            payer_name = user_name or "someone"
            notification_msg = (
                f"Hey {name}! 👋\n\n"
                f"You owe ₹{participant_amount} to {payer_name} "
                f"for their recent expense.\n\n"
                f"— Sent via Settli 💰"
            )
            notification_tasks.append(
                _send_and_track(
                    phone=phone,
                    message=notification_msg,
                    share_detail=share_details[-1],
                    user_id=user_id,
                    message_sid=message_sid,
                    participant_name=name,
                )
            )
        else:
            # Contact not found — note it
            share_details.append(
                ShareDetail(
                    name=name,
                    phone=None,
                    amount=participant_amount,
                    notified=False,
                )
            )
            logger.warning("Contact not found: %s (owner=%s)", name, user_id)

    # Send all notifications concurrently
    if notification_tasks:
        await asyncio.gather(*notification_tasks, return_exceptions=True)

    # Build response message
    notified_names = [s.name for s in share_details if s.notified]
    not_found_names = [s.name for s in share_details if s.phone is None and s.name != (user_name or "You")]

    msg_parts = [f"💰 Split ₹{total} ({num_people} ways):"]
    for s in share_details:
        status = "✅ notified" if s.notified else ("❌ no contact" if s.phone is None and s.name != (user_name or "You") else "you")
        msg_parts.append(f"  • {s.name}: ₹{s.amount} ({status})")

    if not_found_names:
        msg_parts.append(
            f"\n⚠️ Couldn't notify: {', '.join(not_found_names)}. "
            f"Add them with: add contact <name> <phone>"
        )

    return SplitBillOutput(
        expense_id=expense_id,
        total=total,
        shares=share_details,
        message="\n".join(msg_parts),
    )


async def _send_and_track(
    phone: str,
    message: str,
    share_detail: ShareDetail,
    user_id: UUID,
    message_sid: str | None,
    participant_name: str,
) -> None:
    """Send a WhatsApp notification and update the share detail."""
    try:
        await send_whatsapp_message(phone, message)
        share_detail.notified = True

        # Audit log the outbound notification
        await db.insert_audit_log(
            user_id=user_id,
            message_sid=message_sid,
            tool_name="split_bill_notification",
            tool_input={
                "participant": participant_name,
                "phone": phone,
                "amount": str(share_detail.amount),
            },
            tool_output={"status": "sent"},
            status="success",
        )
        logger.info("Notified %s (%s) about split", participant_name, phone)

    except Exception as e:
        logger.error("Failed to notify %s: %s", participant_name, e)
        await db.insert_audit_log(
            user_id=user_id,
            message_sid=message_sid,
            tool_name="split_bill_notification",
            tool_input={
                "participant": participant_name,
                "phone": phone,
                "amount": str(share_detail.amount),
            },
            tool_output={"status": "error", "error": str(e)},
            status="error",
        )
