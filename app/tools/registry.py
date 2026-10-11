"""Tool registry — maps tool names to their execute functions.

This is the single source of truth for which tools exist. The agent layer
uses this registry to dispatch tool calls. Any tool name not in this
registry is rejected.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from app.models.agent import ToolCall

logger = logging.getLogger(__name__)

# Type alias for a tool function
ToolFunction = Callable[..., Coroutine[Any, Any, Any]]

# The registry: tool name → function
_REGISTRY: dict[str, ToolFunction] = {}


def register_tool(name: str) -> Callable[[ToolFunction], ToolFunction]:
    """Decorator to register a tool function."""

    def decorator(func: ToolFunction) -> ToolFunction:
        _REGISTRY[name] = func
        logger.debug("Registered tool: %s", name)
        return func

    return decorator


def get_tool(name: str) -> ToolFunction | None:
    """Look up a tool by name. Returns None if not found."""
    return _REGISTRY.get(name)


def get_all_tools() -> dict[str, ToolFunction]:
    """Return all registered tools."""
    return dict(_REGISTRY)


class UnknownToolError(Exception):
    """Raised when the LLM tries to call a tool that doesn't exist."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Unknown tool: {tool_name}")


async def execute_tool(
    tool_call: ToolCall,
    user_id: UUID,
    message_sid: str | None = None,
    user_phone: str | None = None,
    user_name: str | None = None,
) -> Any:
    """Execute a tool call, routing to the correct function.

    Raises:
        UnknownToolError: if the tool name is not in the registry.
        ValidationError: if the tool args don't match the Pydantic schema.
    """
    func = get_tool(tool_call.tool)
    if func is None:
        raise UnknownToolError(tool_call.tool)

    logger.info("Executing tool: %s with args: %s", tool_call.tool, tool_call.args)

    # Pass common context to all tools
    kwargs: dict[str, Any] = {
        "user_id": user_id,
        "args": tool_call.args,
        "message_sid": message_sid,
    }

    # split_bill needs extra context
    if tool_call.tool == "split_bill":
        kwargs["user_phone"] = user_phone
        kwargs["user_name"] = user_name

    return await func(**kwargs)


def register_all_tools() -> None:
    """Import and register all tool modules.

    Called once at app startup. Using explicit imports rather than
    auto-discovery to keep things transparent.
    """
    from app.tools.get_summary import get_summary
    from app.tools.log_expense import log_expense
    from app.tools.set_budget import set_budget
    from app.tools.set_reminder import set_reminder
    from app.tools.split_bill import split_bill

    _REGISTRY["log_expense"] = log_expense
    _REGISTRY["split_bill"] = split_bill
    _REGISTRY["get_summary"] = get_summary
    _REGISTRY["set_reminder"] = set_reminder
    _REGISTRY["set_budget"] = set_budget

    logger.info("Registered %d tools: %s", len(_REGISTRY), list(_REGISTRY.keys()))
