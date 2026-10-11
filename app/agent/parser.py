"""Parse raw LLM output into the AgentResponse discriminated union.

This module is the safety net: no matter what the LLM returns, it gets
funneled into either a valid ToolCall, a ClarificationRequest, or a
safe fallback. The LLM cannot escape the union.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.agent import AgentResponse, ClarificationRequest, ToolCall

logger = logging.getLogger(__name__)

VALID_TOOLS = frozenset(
    {"log_expense", "split_bill", "get_summary", "set_reminder", "set_budget"}
)


def parse_llm_response(raw: str) -> list[AgentResponse]:
    """Parse the LLM's raw text output into a list of AgentResponse objects.

    Returns:
        A list of ToolCall or ClarificationRequest objects.
        On any parse failure, returns a single ClarificationRequest as fallback.
    """
    raw = raw.strip()

    # Try to extract JSON from the response (handle markdown code blocks)
    json_str = _extract_json(raw)
    if json_str is None:
        logger.warning("No JSON found in LLM response: %s", raw[:200])
        return [_fallback()]

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("JSON decode error in LLM response: %s — %s", e, raw[:200])
        return [_fallback()]

    # Handle clarification response
    if isinstance(parsed, dict):
        if "clarification" in parsed:
            question = str(parsed["clarification"]).strip()
            if question:
                return [ClarificationRequest(question=question)]
            return [_fallback()]

        # Single tool call as a dict
        if "tool" in parsed:
            result = _parse_single_tool_call(parsed)
            return [result] if result else [_fallback()]

        logger.warning("Unexpected dict format from LLM: %s", parsed)
        return [_fallback()]

    # Handle array of tool calls
    if isinstance(parsed, list):
        results: list[AgentResponse] = []
        for item in parsed:
            if isinstance(item, dict) and "tool" in item:
                result = _parse_single_tool_call(item)
                if result:
                    results.append(result)
        return results if results else [_fallback()]

    logger.warning("Unexpected JSON type from LLM: %s", type(parsed))
    return [_fallback()]


def _parse_single_tool_call(data: dict[str, Any]) -> ToolCall | None:
    """Parse a single tool call dict into a ToolCall, or None if invalid."""
    tool_name = str(data.get("tool", "")).strip()
    args = data.get("args", {})

    if tool_name not in VALID_TOOLS:
        logger.warning("Unknown tool name from LLM: %s", tool_name)
        return None

    if not isinstance(args, dict):
        logger.warning("Tool args is not a dict: %s", type(args))
        args = {}

    return ToolCall(tool=tool_name, args=args)  # type: ignore[arg-type]


def _extract_json(text: str) -> str | None:
    """Extract JSON from potentially markdown-wrapped LLM output."""
    # Try raw text first (most common case)
    text = text.strip()
    if text.startswith(("{", "[")):
        return text

    # Try to extract from markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find any JSON object or array in the text
    for pattern in [r"\{.*\}", r"\[.*\]"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0)

    return None


def _fallback() -> ClarificationRequest:
    """Return a safe fallback when the LLM output can't be parsed."""
    return ClarificationRequest(
        question="I didn't quite understand that. Could you rephrase? "
        "For example: 'spent 200 on lunch' or 'how much did I spend this month?'"
    )
