"""Tests for the penny-perfect split math.

Verifies that Decimal arithmetic ensures sum(shares) == total
without floating point rounding errors.
"""

from decimal import Decimal

from app.tools.split_math import calculate_split


class TestSplitMath:
    """Test calculate_split with various inputs."""

    def test_even_split(self) -> None:
        """Exact division with no remainder."""
        result = calculate_split(Decimal("100"), 4)
        assert len(result) == 4
        assert all(s == Decimal("25") for s in result)
        assert sum(result) == Decimal("100")

    def test_three_way_split_250(self) -> None:
        """250 split 3 ways (83.34 + 83.33 + 83.33)."""
        result = calculate_split(Decimal("250"), 3)
        assert len(result) == 3
        assert result[0] == Decimal("83.34")
        assert result[1] == Decimal("83.33")
        assert result[2] == Decimal("83.33")
        assert sum(result) == Decimal("250")

    def test_three_way_split_100(self) -> None:
        """100 split 3 ways (33.34 + 33.33 + 33.33)."""
        result = calculate_split(Decimal("100"), 3)
        assert len(result) == 3
        assert result[0] == Decimal("33.34")
        assert result[1] == Decimal("33.33")
        assert result[2] == Decimal("33.33")
        assert sum(result) == Decimal("100")

    def test_four_way_split_exact(self) -> None:
        """10 split 4 ways (2.50 each)."""
        result = calculate_split(Decimal("10"), 4)
        assert len(result) == 4
        assert all(s == Decimal("2.50") for s in result)
        assert sum(result) == Decimal("10")

    def test_uneven_split_remainder(self) -> None:
        """Verify remainder pennies are distributed to first people."""
        # 100 split 7: base = 14.28, remainder = 0.04 = 4 pennies
        # So first 4 get +0.01: 14.29, 14.29, 14.29, 14.29, 14.28, 14.28, 14.28
        result = calculate_split(Decimal("100"), 7)
        assert len(result) == 7
        assert sum(result) == Decimal("100")
        assert result[0] == Decimal("14.29")
        assert result[1] == Decimal("14.29")
        assert result[2] == Decimal("14.29")
        assert result[3] == Decimal("14.29")
        assert result[4] == Decimal("14.28")
        assert result[5] == Decimal("14.28")
        assert result[6] == Decimal("14.28")

    def test_single_person(self) -> None:
        """Split among 1 person (the whole amount)."""
        result = calculate_split(Decimal("500"), 1)
        assert result == [Decimal("500")]
        assert sum(result) == Decimal("500")

    def test_large_amount(self) -> None:
        """Large amount with many decimal places."""
        result = calculate_split(Decimal("999999.99"), 3)
        assert len(result) == 3
        assert sum(result) == Decimal("999999.99")

    def test_invalid_num_people_zero(self) -> None:
        """Zero people raises ValueError."""
        from decimal import Decimal as D

        try:
            calculate_split(D("100"), 0)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "at least 1" in str(e)

    def test_invalid_negative_amount(self) -> None:
        """Negative amount raises ValueError."""
        from decimal import Decimal as D

        try:
            calculate_split(D("-100"), 2)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "positive" in str(e)

    def test_fractional_amount_exact(self) -> None:
        """Fractional amounts that divide evenly."""
        result = calculate_split(Decimal("123.45"), 5)
        assert len(result) == 5
        assert sum(result) == Decimal("123.45")
        assert result[0] == Decimal("24.69")

    def test_fractional_amount_remainder(self) -> None:
        """Fractional amounts with remainder pennies."""
        result = calculate_split(Decimal("123.46"), 5)
        assert len(result) == 5
        assert sum(result) == Decimal("123.46")
        # 123.46 / 5 = 24.692, rounds down to 24.69, remainder 0.01
        assert result[0] == Decimal("24.70")
        assert result[1] == Decimal("24.69")
        assert result[2] == Decimal("24.69")
        assert result[3] == Decimal("24.69")
        assert result[4] == Decimal("24.69")

    def test_penny_perfect_invariant(self) -> None:
        """Verify the "penny-perfect" claim for various splits."""
        test_cases = [
            (Decimal("250"), 3),
            (Decimal("100"), 3),
            (Decimal("99"), 7),
            (Decimal("1234.56"), 8),
            (Decimal("1000"), 3),
            (Decimal("750.75"), 4),
        ]

        for total, num_people in test_cases:
            result = calculate_split(total, num_people)
            # Invariant: sum must equal total exactly
            assert sum(result) == total, f"Failed for {total}/{num_people}: sum={sum(result)}"
