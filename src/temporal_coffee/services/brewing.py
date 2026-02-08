"""Brewing service facade."""

import asyncio
import logging
import random

from temporal_coffee.domain.models import BrewInput

logger = logging.getLogger(__name__)


class BrewService:
    """Simulates brewing a coffee drink.

    Randomly fails ~30% of the time to demonstrate Temporal retries.
    """

    async def brew(self, input: BrewInput) -> bool:
        logger.info("Brewing %s (%s) for order %s", input.drink, input.size.value, input.order_id)
        await asyncio.sleep(1.0)
        if random.random() < 0.3:  # noqa: S311
            raise RuntimeError(f"Brew machine jammed for order {input.order_id}!")
        logger.info("Brew complete for order %s", input.order_id)
        return True
