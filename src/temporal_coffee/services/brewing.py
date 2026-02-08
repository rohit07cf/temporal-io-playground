"""
Brewing service facade.

Simulates a coffee brewing machine. Intentionally fails ~30% of the time
to demonstrate Temporal's automatic activity retry mechanism.

Randomness is confined to this service layer — never in workflows (which
must be deterministic) and not in activities directly (to keep them as
thin wrappers).
"""

import asyncio
import logging
import random

from temporal_coffee.domain.models import BrewInput

logger = logging.getLogger(__name__)


class BrewService:
    """Simulates brewing a coffee drink.

    Randomly fails ~30% of the time to demonstrate Temporal retries.
    When this raises, the activity (brew_coffee) propagates the exception,
    and Temporal's retry policy kicks in automatically.
    """

    async def brew(self, input: BrewInput) -> bool:
        logger.info("Brewing %s (%s) for order %s", input.drink, input.size.value, input.order_id)
        await asyncio.sleep(1.0)  # Simulate brewing time
        if random.random() < 0.3:  # noqa: S311 — intentional demo randomness
            raise RuntimeError(f"Brew machine jammed for order {input.order_id}!")
        logger.info("Brew complete for order %s", input.order_id)
        return True
