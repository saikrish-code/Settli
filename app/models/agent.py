"""Agent response models — the discriminated union that constrains LLM output.

The LLM may ONLY produce one of these two response types:
  1. ToolCall  — invoke a named tool with validated arguments
  2. ClarificationRequest — ask the user for more information

Anything else is rejected by the parser.
"""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A request from the LLM to invoke one of the five permitted tools."""

    type: Literal["tool_call"] = "tool_call"
    tool: Literal["log_expense", "split_bill", "get_summary", "set_reminder", "set_budget"]
    args: dict[str, Any] = Field(default_factory=dict)


class ClarificationRequest(BaseModel):
    """The LLM needs more information from the user before it can act."""

    type: Literal["clarification"] = "clarification"
    question: str = Field(..., min_length=1)


# The discriminated union — the ONLY valid LLM outputs
AgentResponse = Union[ToolCall, ClarificationRequest]


class AgentResult(BaseModel):
    """The full result after processing an LLM response.

    May contain multiple tool calls (e.g., log_expense + split_bill)
    or a single clarification request.
    """

    actions: list[AgentResponse] = Field(default_factory=list)
    reply_text: str = Field(
        default="I'm not sure how to help with that. Could you rephrase?",
        description="The final text reply sent to the user via WhatsApp",
    )
