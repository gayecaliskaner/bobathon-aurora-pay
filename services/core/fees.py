"""Transfer fee calculation. See docs/FEE-POLICY.md."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
THRESHOLD = Decimal("1000.00")
RATE_BELOW_THRESHOLD = Decimal("0.005")
RATE_AT_OR_ABOVE_THRESHOLD = Decimal("0.0025")


def fee_for(amount: Decimal) -> Decimal:
    rate = RATE_AT_OR_ABOVE_THRESHOLD if amount >= THRESHOLD else RATE_BELOW_THRESHOLD
    return (amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)
