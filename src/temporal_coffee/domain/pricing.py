"""
Pricing strategies (Strategy pattern).

The Strategy pattern allows swapping pricing logic without changing the
workflow. The workflow holds a reference to `PricingStrategy` (a Protocol)
and calls `price_cents()`. To add a new pricing scheme (e.g. happy-hour
discounts), implement the protocol and inject it into the workflow.

IMPORTANT: Pricing runs directly inside the workflow (not in an activity),
so it MUST be deterministic — no I/O, no randomness, no system clock.
"""

from typing import Protocol

from temporal_coffee.domain.models import DrinkSize, OrderRequest


class PricingStrategy(Protocol):
    """Interface for computing the price of an order.

    Any class with a `price_cents(req) -> int` method satisfies this
    protocol (structural subtyping — no explicit inheritance needed).
    """

    def price_cents(self, req: OrderRequest) -> int: ...


class StandardPricingStrategy:
    """Default pricing: base price by size + surcharge for specialty drinks.

    Examples:
        - Small espresso:  300 cents ($3.00)
        - Medium latte:    450 + 75 = 525 cents ($5.25)
        - Large mocha:     600 + 75 = 675 cents ($6.75)
    """

    BASE_PRICES: dict[DrinkSize, int] = {
        DrinkSize.S: 300,   # $3.00
        DrinkSize.M: 450,   # $4.50
        DrinkSize.L: 600,   # $6.00
    }
    # Specialty drinks that incur an extra surcharge
    SURCHARGE_KEYWORDS: set[str] = {"latte", "mocha"}
    SURCHARGE_CENTS: int = 75  # $0.75

    def price_cents(self, req: OrderRequest) -> int:
        base = self.BASE_PRICES[req.size]
        drink_lower = req.drink.lower()
        if any(kw in drink_lower for kw in self.SURCHARGE_KEYWORDS):
            base += self.SURCHARGE_CENTS
        return base
