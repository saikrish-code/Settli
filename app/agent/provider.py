"""LLM Provider Protocol and concrete implementations.

Three providers, selectable via env var:
  - OpenAIProvider  (gpt-4o-mini)
  - GroqProvider    (llama-3.3-70b)
  - LocalMockProvider (deterministic regex, zero cost for CI)
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Protocol, runtime_checkable

from app.agent.parser import parse_llm_response
from app.agent.system_prompt import get_system_prompt
from app.config import settings
from app.models.agent import AgentResponse

logger = logging.getLogger(__name__)


def _compute_next_5th(today: date) -> str:
    """Compute the next 5th of the month from today."""
    if today.day < 5:
        return today.replace(day=5).isoformat()
    # Next month's 5th
    if today.month == 12:
        return today.replace(year=today.year + 1, month=1, day=5).isoformat()
    return today.replace(month=today.month + 1, day=5).isoformat()


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers. Any class implementing classify() is valid."""

    async def classify(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> list[AgentResponse]: ...


class OpenAIProvider:
    """Uses the OpenAI API (gpt-4o-mini by default)."""

    def __init__(self) -> None:
        # Lazy import to avoid import errors when openai isn't used
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def classify(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> list[AgentResponse]:
        today = date.today()
        system_prompt = get_system_prompt(
            today=today.isoformat(), next_5th=_compute_next_5th(today)
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.1,
                max_tokens=500,
            )
            raw = response.choices[0].message.content or ""
            logger.info("OpenAI response: %s", raw[:300])
            return parse_llm_response(raw)
        except Exception:
            logger.exception("OpenAI API error")
            return parse_llm_response("")


class GroqProvider:
    """Uses the Groq API (llama-3.3-70b by default)."""

    def __init__(self) -> None:
        from groq import AsyncGroq

        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    async def classify(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> list[AgentResponse]:
        today = date.today()
        system_prompt = get_system_prompt(
            today=today.isoformat(), next_5th=_compute_next_5th(today)
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.1,
                max_tokens=500,
            )
            raw = response.choices[0].message.content or ""
            logger.info("Groq response: %s", raw[:300])
            return parse_llm_response(raw)
        except Exception:
            logger.exception("Groq API error")
            return parse_llm_response("")


class LocalMockProvider:
    """Deterministic regex-based provider for testing without API costs.

    Matches common expense patterns and returns pre-built tool calls.
    Used in CI and local development with LLM_PROVIDER=mock.
    """

    async def classify(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> list[AgentResponse]:
        msg = message.strip().lower()
        return parse_llm_response(self._match(msg))

    def _match(self, msg: str) -> str:
        """Match the message to a tool call using regex patterns."""
        import json

        # ── Expense with split ──
        split_match = re.match(
            r"(?:spent|paid)\s+(\d+(?:\.\d+)?)\s+(?:on|for)\s+(.+?)\s+"
            r"(?:with|split\s+(?:with|between))\s+(.+?)(?:,\s*split\s+\d+\s+ways?)?$",
            msg,
        )
        if split_match:
            amount = float(split_match.group(1))
            desc = split_match.group(2).strip().rstrip(",")
            names_str = split_match.group(3).strip()
            names = [n.strip().title() for n in re.split(r"\s+and\s+|,\s*", names_str) if n.strip()]
            return json.dumps(
                [
                    {
                        "tool": "log_expense",
                        "args": {
                            "amount": amount,
                            "category": "general",
                            "description": desc,
                            "split_with": names,
                        },
                    }
                ]
            )

        # ── Simple expense ──
        expense_match = re.match(
            r"(?:spent|paid)\s+(\d+(?:\.\d+)?)\s+(?:on|for)\s+(.+)$", msg
        )
        if expense_match:
            amount = float(expense_match.group(1))
            desc = expense_match.group(2).strip()
            # Try to infer category
            category = self._infer_category(desc)
            return json.dumps(
                [
                    {
                        "tool": "log_expense",
                        "args": {
                            "amount": amount,
                            "category": category,
                            "description": desc,
                        },
                    }
                ]
            )

        # ── Summary ──
        if any(kw in msg for kw in ["how much", "summary", "total", "spending"]):
            period = "this_month"
            if "today" in msg:
                period = "today"
            elif "week" in msg:
                period = "this_week"
            elif "last month" in msg:
                period = "last_month"
            return json.dumps([{"tool": "get_summary", "args": {"period": period}}])

        # ── Reminder ──
        reminder_match = re.match(
            r"remind\s+me\s+(?:to\s+)?(.+?)(?:\s+on\s+the\s+(\d+)(?:th|st|nd|rd)?)?$",
            msg,
        )
        if reminder_match:
            reminder_msg = reminder_match.group(1).strip()
            day = reminder_match.group(2)
            today = date.today()
            if day:
                d = int(day)
                if d <= today.day:
                    if today.month == 12:
                        remind_date = today.replace(year=today.year + 1, month=1, day=d)
                    else:
                        remind_date = today.replace(month=today.month + 1, day=d)
                else:
                    remind_date = today.replace(day=d)
            else:
                remind_date = today + timedelta(days=1)
            return json.dumps(
                [
                    {
                        "tool": "set_reminder",
                        "args": {
                            "message": reminder_msg.title(),
                            "remind_at": f"{remind_date.isoformat()}T09:00:00",
                        },
                    }
                ]
            )

        # ── Budget ──
        budget_match = re.match(
            r"set\s+(?:my\s+)?(\w+)\s+budget\s+(?:to\s+)?(\d+(?:\.\d+)?)", msg
        )
        if budget_match:
            category = budget_match.group(1).strip()
            limit = float(budget_match.group(2))
            return json.dumps(
                [
                    {
                        "tool": "set_budget",
                        "args": {"category": category, "monthly_limit": limit},
                    }
                ]
            )

        # ── Ambiguous / unknown → clarification ──
        return json.dumps(
            {
                "clarification": (
                    "I didn't quite understand that. Could you rephrase? "
                    "For example: 'spent 200 on lunch' or 'how much did I spend this month?'"
                )
            }
        )

    def _infer_category(self, description: str) -> str:
        """Simple keyword-based category inference."""
        desc = description.lower()
        categories = {
            "food": ["chai", "coffee", "lunch", "dinner", "breakfast", "snack", "biryani", "pizza", "burger"],
            "transport": ["uber", "ola", "auto", "cab", "bus", "metro", "fuel", "petrol", "diesel"],
            "entertainment": ["movie", "netflix", "spotify", "game", "concert", "show"],
            "shopping": ["clothes", "shoes", "amazon", "flipkart", "online"],
            "bills": ["electricity", "water", "internet", "wifi", "phone", "recharge"],
            "health": ["medicine", "doctor", "hospital", "gym", "pharmacy"],
            "rent": ["rent"],
        }
        for cat, keywords in categories.items():
            if any(kw in desc for kw in keywords):
                return cat
        return "general"


def get_provider() -> LLMProvider:
    """Factory function: returns the configured LLM provider."""
    from app.config import LLMProviderType

    if settings.llm_provider == LLMProviderType.OPENAI:
        logger.info("Using OpenAI provider (model=%s)", settings.openai_model)
        return OpenAIProvider()
    elif settings.llm_provider == LLMProviderType.GROQ:
        logger.info("Using Groq provider (model=%s)", settings.groq_model)
        return GroqProvider()
    else:
        logger.info("Using LocalMockProvider (no API calls)")
        return LocalMockProvider()
