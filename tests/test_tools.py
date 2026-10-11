"""Tests for tools."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.tools.log_expense import log_expense
from app.tools.get_summary import get_summary
from app.tools.set_reminder import set_reminder
from app.tools.set_budget import set_budget
from app.tools.split_bill import split_bill


@pytest.mark.asyncio
class TestLogExpense:
    """Test log_expense tool."""

    async def test_log_expense_success(self):
        """Log an expense successfully."""
        user_id = uuid4()
        args = {
            "amount": "250",
            "category": "food",
            "description": "chai",
        }

        with patch("app.tools.log_expense.db") as mock_db:
            mock_db.insert_expense = AsyncMock(
                return_value={"id": uuid4(), "amount": Decimal("250")}
            )
            mock_db.get_budget = AsyncMock(return_value=None)
            mock_db.get_category_total_this_month = AsyncMock(
                return_value=Decimal("0")
            )

            result = await log_expense(user_id, args)

            assert result is not None
            assert result.amount == Decimal("250")
            assert result.category == "food"
            assert "logged" in result.message.lower()

    async def test_log_expense_with_split(self):
        """Log an expense with split participants."""
        user_id = uuid4()
        args = {
            "amount": "300",
            "category": "dinner",
            "description": "biryani",
            "split_with": ["Raj", "Priya"],
        }

        with patch("app.tools.log_expense.db") as mock_db:
            mock_db.insert_expense = AsyncMock(
                return_value={"id": uuid4(), "amount": Decimal("300")}
            )
            mock_db.get_budget = AsyncMock(return_value=None)

            result = await log_expense(user_id, args)

            assert result.amount == Decimal("300")
            assert "splitting" in result.message.lower()

    async def test_log_expense_budget_warning(self):
        """Budget alert when over 80% of limit."""
        user_id = uuid4()
        args = {"amount": "2500", "category": "food", "description": "lunch"}

        with patch("app.tools.log_expense.db") as mock_db:
            mock_db.insert_expense = AsyncMock(
                return_value={"id": uuid4(), "amount": Decimal("2500")}
            )
            mock_db.get_budget = AsyncMock(
                return_value={"monthly_limit": Decimal("3000")}
            )
            mock_db.get_category_total_this_month = AsyncMock(
                return_value=Decimal("2500")
            )

            result = await log_expense(user_id, args)

            assert result.budget_warning is not None
            assert "80%" in result.budget_warning.lower() or "heads up" in result.budget_warning.lower()


@pytest.mark.asyncio
class TestGetSummary:
    """Test get_summary tool."""

    async def test_get_summary_this_month(self):
        """Get monthly expense summary."""
        user_id = uuid4()
        args = {"period": "this_month"}

        with patch("app.tools.get_summary.db") as mock_db:
            mock_db.get_total_by_period = AsyncMock(
                return_value={"total": Decimal("1250"), "count": 5}
            )
            mock_db.get_category_totals = AsyncMock(
                return_value=[{"category": "food", "total": Decimal("800")}]
            )

            result = await get_summary(user_id, args)

            assert result.period == "this_month"
            assert result.total == Decimal("1250")
            assert result.expense_count == 5

    async def test_get_summary_today(self):
        """Get today's expense summary."""
        user_id = uuid4()
        args = {"period": "today"}

        with patch("app.tools.get_summary.db") as mock_db:
            mock_db.get_total_by_period = AsyncMock(
                return_value={"total": Decimal("150"), "count": 2}
            )
            mock_db.get_category_totals = AsyncMock(return_value=[])

            result = await get_summary(user_id, args)

            assert result.period == "today"
            assert result.total == Decimal("150")


@pytest.mark.asyncio
class TestSetReminder:
    """Test set_reminder tool."""

    async def test_set_reminder_success(self):
        """Set a reminder successfully."""
        user_id = uuid4()
        args = {
            "message": "Pay rent",
            "remind_at": "2026-11-05T09:00:00",
        }

        with patch("app.tools.set_reminder.db") as mock_db:
            mock_db.insert_reminder = AsyncMock(
                return_value={"id": uuid4()}
            )

            result = await set_reminder(user_id, args)

            assert result is not None
            assert "Pay rent" in result.message


@pytest.mark.asyncio
class TestSetBudget:
    """Test set_budget tool."""

    async def test_set_budget_success(self):
        """Set a budget successfully."""
        user_id = uuid4()
        args = {"category": "food", "monthly_limit": "3000"}

        with patch("app.tools.set_budget.db") as mock_db:
            mock_db.upsert_budget = AsyncMock(
                return_value={"id": uuid4()}
            )

            result = await set_budget(user_id, args)

            assert result is not None
            assert result.category == "food"
            assert result.monthly_limit == Decimal("3000")


@pytest.mark.asyncio
class TestSplitBill:
    """Test split_bill tool."""

    async def test_split_bill_success(self):
        """Split a bill successfully."""
        user_id = uuid4()
        args = {
            "expense_id": str(uuid4()),
            "participants": ["Raj", "Priya"],
            "total": "300",
        }

        with patch("app.tools.split_bill.db") as mock_db:
            with patch("app.tools.split_bill.send_whatsapp_message", new_callable=AsyncMock):
                mock_db.get_contact_by_name = AsyncMock(
                    return_value={"phone": "+919876543210"}
                )

                result = await split_bill(user_id, args)

                assert result.total == Decimal("300")
                assert len(result.shares) == 3
                assert sum(s.amount for s in result.shares) == Decimal("300")

    async def test_split_bill_unknown_participant(self):
        """Split a bill with unknown participant."""
        user_id = uuid4()
        args = {
            "expense_id": str(uuid4()),
            "participants": ["Unknown"],
            "total": "100",
        }

        with patch("app.tools.split_bill.db") as mock_db:
            with patch("app.tools.split_bill.send_whatsapp_message", new_callable=AsyncMock):
                mock_db.get_contact_by_name = AsyncMock(return_value=None)

                result = await split_bill(user_id, args)

                assert result.total == Decimal("100")
                assert len(result.shares) == 2

    async def test_split_bill_penny_perfect(self):
        """Verify penny-perfect split."""
        user_id = uuid4()
        args = {
            "expense_id": str(uuid4()),
            "participants": ["Raj", "Priya"],
            "total": "100",
        }

        with patch("app.tools.split_bill.db") as mock_db:
            with patch("app.tools.split_bill.send_whatsapp_message", new_callable=AsyncMock):
                mock_db.get_contact_by_name = AsyncMock(
                    return_value={"phone": "+919876543210"}
                )

                result = await split_bill(user_id, args)

                assert sum(s.amount for s in result.shares) == Decimal("100")