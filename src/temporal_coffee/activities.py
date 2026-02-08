"""Temporal activities — thin wrappers delegating to service layer."""

import logging

from temporalio import activity

from temporal_coffee.domain.models import BrewInput, ChargeInput, ReceiptInput
from temporal_coffee.services.factory import ServiceFactory

logger = logging.getLogger(__name__)


@activity.defn
async def charge_customer(input: ChargeInput) -> bool:
    """Charge the customer via PaymentService."""
    logger.info("Activity charge_customer started for order %s", input.order_id)
    result = await ServiceFactory.get_payment_service().charge(input)
    logger.info("Activity charge_customer completed for order %s", input.order_id)
    return result


@activity.defn
async def brew_coffee(input: BrewInput) -> bool:
    """Brew the coffee via BrewService (may fail and trigger retries)."""
    logger.info("Activity brew_coffee started for order %s", input.order_id)
    result = await ServiceFactory.get_brew_service().brew(input)
    logger.info("Activity brew_coffee completed for order %s", input.order_id)
    return result


@activity.defn
async def send_receipt(input: ReceiptInput) -> bool:
    """Send receipt via NotificationService."""
    logger.info("Activity send_receipt started for order %s", input.order_id)
    result = await ServiceFactory.get_notification_service().send_receipt(input)
    logger.info("Activity send_receipt completed for order %s", input.order_id)
    return result
