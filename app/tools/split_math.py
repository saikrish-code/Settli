"""Penny-perfect bill splitting with Decimal arithmetic.

The key invariant: sum(shares) == total, always.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal


def calculate_split(total: Decimal, num_people: int) -> list[Decimal]:
    """Split a total amount among num_people, distributing remainder pennies.

    Args:
        total: The total amount to split (must be positive).
        num_people: Number of people to split among (must be >= 1).

    Returns:
        A list of Decimal amounts, one per person.
        The first N people absorb the remainder pennies so the sum is exact.

    Examples:
        >>> calculate_split(Decimal("250"), 3)
        [Decimal('83.34'), Decimal('83.33'), Decimal('83.33')]

        >>> calculate_split(Decimal("100"), 3)
        [Decimal('33.34'), Decimal('33.33'), Decimal('33.33')]

        >>> calculate_split(Decimal("10"), 4)
        [Decimal('2.50'), Decimal('2.50'), Decimal('2.50'), Decimal('2.50')]
    """
    if num_people < 1:
        raise ValueError("num_people must be at least 1")
    if total <= 0:
        raise ValueError("total must be positive")

    # Base share rounded down to 2 decimal places
    base = (total / num_people).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    # Remainder after giving everyone the base amount
    remainder = total - (base * num_people)

    # Convert remainder to whole pennies (paisa)
    pennies = int(remainder * 100)

    # Build shares: first `pennies` people each get an extra 0.01
    shares = [base] * num_people
    for i in range(pennies):
        shares[i] += Decimal("0.01")

    # Sanity check: the invariant must hold
    assert sum(shares) == total, f"Split invariant violated: {sum(shares)} != {total}"

    return shares
