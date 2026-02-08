"""
Temporal activities — thin wrappers delegating to the service layer.

An **activity** is a single unit of work in a Temporal workflow. Activities are
where side-effects happen: network calls, database writes, file I/O, etc.

Key points:
  - Decorated with `@activity.defn` so Temporal can discover and invoke them.
  - Executed by a **worker** in response to tasks from a **task queue**.
  - If an activity raises an exception, Temporal retries it automatically
    according to the RetryPolicy configured in the workflow.
  - Activities run OUTSIDE the deterministic workflow sandbox, so they can
    use `random`, `datetime.now()`, network I/O, etc. freely.
  - Each activity accepts a single Pydantic model as input. The Temporal SDK
    serializes it to JSON (via pydantic_data_converter) when dispatching the
    task and deserializes it back when the worker picks it up.
"""

import logging

# `activity` provides the @activity.defn decorator that registers a function
# as a Temporal activity. The function name becomes the activity type name
# on the Temporal server (e.g. "charge_customer").
from temporalio import activity

from temporal_coffee.domain.models import BrewInput, ChargeInput, ReceiptInput
from temporal_coffee.services.factory import ServiceFactory

logger = logging.getLogger(__name__)


@activity.defn
async def charge_customer(input: ChargeInput) -> bool:
    """Charge the customer via PaymentService.

    Delegates to PaymentService.charge(). Always succeeds in this demo.
    On failure the workflow's retry policy would kick in automatically.
    """
    logger.info("Activity charge_customer started for order %s", input.order_id)
    result = await ServiceFactory.get_payment_service().charge(input)
    logger.info("Activity charge_customer completed for order %s", input.order_id)
    return result


@activity.defn
async def brew_coffee(input: BrewInput) -> bool:
    """Brew the coffee via BrewService.

    BrewService randomly fails ~30% of the time to simulate a flaky
    downstream dependency. When it raises, Temporal catches the exception
    and retries the activity according to the workflow's RetryPolicy
    (up to 5 attempts with exponential backoff).
    """
    logger.info("Activity brew_coffee started for order %s", input.order_id)
    result = await ServiceFactory.get_brew_service().brew(input)
    logger.info("Activity brew_coffee completed for order %s", input.order_id)
    return result


@activity.defn
async def send_receipt(input: ReceiptInput) -> bool:
    """Send receipt via NotificationService.

    Delegates to NotificationService.send_receipt(). Always succeeds in
    this demo.
    """
    logger.info("Activity send_receipt started for order %s", input.order_id)
    result = await ServiceFactory.get_notification_service().send_receipt(input)
    logger.info("Activity send_receipt completed for order %s", input.order_id)
    return result
