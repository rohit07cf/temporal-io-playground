"""
Payment service facade.

Part of the **service layer** that encapsulates external operations behind
clean interfaces. In a real system this would call Stripe, Square, etc.
Here it simulates the call with a short sleep.

Activities delegate to services (not the other way around), keeping the
Temporal-specific code separate from business logic.
"""

import asyncio
import logging

from temporal_coffee.domain.models import ChargeInput

logger = logging.getLogger(__name__)


class PaymentService:
    """Simulates charging a customer.

    Always succeeds in this demo. In production, failures here would
    propagate up through the activity and be retried by Temporal.
    """

    async def charge(self, input: ChargeInput) -> bool:
        logger.info("Charging order %s for %d cents", input.order_id, input.amount_cents)
        await asyncio.sleep(0.5)  # Simulate network latency
        logger.info("Charge successful for order %s", input.order_id)
        return True
