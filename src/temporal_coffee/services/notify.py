"""
Notification service facade.

Simulates sending an order receipt (e.g. via email or push notification).
In production this would integrate with SendGrid, Twilio, etc.
"""

import asyncio
import logging

from temporal_coffee.domain.models import ReceiptInput

logger = logging.getLogger(__name__)


class NotificationService:
    """Simulates sending a receipt to the customer."""

    async def send_receipt(self, input: ReceiptInput) -> bool:
        logger.info("Sending receipt for order %s", input.order_id)
        await asyncio.sleep(0.3)  # Simulate network latency
        logger.info("Receipt sent for order %s", input.order_id)
        return True
