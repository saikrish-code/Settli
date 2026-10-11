"""Tests for the LLM response parser.

Tests the discriminated union: ToolCall | ClarificationRequest.
Verifies that valid outputs are parsed correctly and invalid outputs
fall back to clarification.
"""

from app.agent.parser import parse_llm_response
from app.models.agent import AgentResponse, ClarificationRequest, ToolCall


class TestParseLLMResponse:
    """Test parse_llm_response with various inputs."""

    def test_valid_single_tool_call(self) -> None:
        """Parse a single tool call as a dict."""
        raw = '{"tool": "log_expense", "args": {"amount": 250, "category": "food", "description": "lunch"}}'
        result = parse_llm_response(raw)

        assert len(result) == 1
        assert isinstance(result[0], ToolCall)
        assert result[0].tool == "log_expense"
        assert result[0].args["amount"] == 250

    def test_valid_multiple_tool_calls(self) -> None:
        """Parse an array of tool calls."""
        raw = (
            '[{"tool": "log_expense", "args": {"amount": 250, "category": "food", "description": "chai"}}'
            ', {"tool": "get_summary", "args": {"period": "this_month"}}]'
        )
        result = parse_llm_response(raw)

        assert len(result) == 2
        assert all(isinstance(r, ToolCall) for r in result)
        assert result[0].tool == "log_expense"
        assert result[1].tool == "get_summary"

    def test_valid_clarification_request(self) -> None:
        """Parse a clarification request."""
        raw = '{"clarification": "How much did you spend?"}'
        result = parse_llm_response(raw)

        assert len(result) == 1
        assert isinstance(result[0], ClarificationRequest)
        assert result[0].question == "How much did you spend?"

    def test_markdown_wrapped_json(self) -> None:
        """Parse JSON wrapped in markdown code blocks."""
        raw = '```json\n{"tool": "log_expense", "args": {"amount": 100, "category": "food", "description": "tea"}}\n```'
        result = parse_llm_response(raw)

        assert len(result) == 1
        assert isinstance(result[0], ToolCall)
        assert result[0].tool == "log_expense"

    def test_unknown_tool_rejected(self) -> None:
        """Unknown tool names fall back to clarification."""
        raw = '{"tool": "unknown_tool", "args": {}}'
        result = parse_llm_response(raw)

        # Should fallback to clarification
        assert len(result) == 1
        assert isinstance(result[0], ClarificationRequest)

    def test_invalid_json_fallback(self) -> None:
        """Invalid JSON falls back to clarification."""
        raw = "not valid json at all"
        result = parse_llm_response(raw)

        assert len(result) == 1
        assert isinstance(result[0], ClarificationRequest)

    def test_empty_string_fallback(self) -> None:
        """Empty string falls back to clarification."""
        result = parse_llm_response("")

        assert len(result) == 1
        assert isinstance(result[0], ClarificationRequest)

    def test_valid_tools_only(self) -> None:
        """Only the 5 allowed tool names are accepted."""
        valid_tools = ["log_expense", "split_bill", "get_summary", "set_reminder", "set_budget"]

        for tool in valid_tools:
            raw = f'{{"tool": "{tool}", "args": {{}}}}'
            result = parse_llm_response(raw)
            assert len(result) == 1
            assert isinstance(result[0], ToolCall)
            assert result[0].tool == tool

    def test_array_with_unknown_tool(self) -> None:
        """Array containing unknown tool should filter it out."""
        raw = (
            '[{"tool": "log_expense", "args": {"amount": 100, "category": "food", "description": "tea"}}'
            ', {"tool": "unknown_tool", "args": {}}]'
        )
        result = parse_llm_response(raw)

        # Only the valid tool should be parsed
        assert len(result) == 1
        assert result[0].tool == "log_expense"
