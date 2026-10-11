"""Audit service — writes every tool invocation to the audit_log table.

This is the foundation for proving the system is auditable:
every action the agent takes is recorded with who, what, when, and result.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.db import operations as db

logger = logging.getLogger(__name__)


async def log_tool_call(
    user_id: UUID | None,
    message_sid: str | None,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: dict[str, Any] | None,
    status: str = "success",
) -> None:
    """Write an audit log entry for a tool invocation.

    Called by the webhook handler after every tool execution,
    whether it succeeds or fails.
    """
    try:
        await db.insert_audit_log(
            user_id=user_id,
            message_sid=message_sid,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            status=status,
        )
    except Exception:
        # Audit logging should never crash the main flow
        logger.exception(
            "Failed to write audit log: tool=%s, user=%s", tool_name, user_id
        )
