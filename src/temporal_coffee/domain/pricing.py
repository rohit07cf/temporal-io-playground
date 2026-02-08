"""Pricing strategies (Strategy pattern)."""

from typing import Protocol

from temporal_coffee.domain.models import DrinkSize, OrderRequest


class PricingStrategy(Protocol):
    """Interface for computing the price of an order."""

    def price_cents(self, req: OrderRequest) -> int: ...


class StandardPricingStrategy:
    """Default pricing: base price by size + surcharge for specialty drinks."""

    BASE_PRICES: dict[DrinkSize, int] = {
        DrinkSize.S: 300,
        DrinkSize.M: 450,
        DrinkSize.L: 600,
    }
    SURCHARGE_KEYWORDS: set[str] = {"latte", "mocha"}
    SURCHARGE_CENTS: int = 75

    def price_cents(self, req: OrderRequest) -> int:
        base = self.BASE_PRICES[req.size]
        drink_lower = req.drink.lower()
        if any(kw in drink_lower for kw in self.SURCHARGE_KEYWORDS):
            base += self.SURCHARGE_CENTS
        return base
