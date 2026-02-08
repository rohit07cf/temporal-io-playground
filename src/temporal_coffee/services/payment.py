"""Payment service facade."""

import asyncio
import logging

from temporal_coffee.domain.models import ChargeInput

logger = logging.getLogger(__name__)


class PaymentService:
    """Simulates charging a customer."""

    async def charge(self, input: ChargeInput) -> bool:
        logger.info("Charging order %s for %d cents", input.order_id, input.amount_cents)
        await asyncio.sleep(0.5)
        logger.info("Charge successful for order %s", input.order_id)
        return True
