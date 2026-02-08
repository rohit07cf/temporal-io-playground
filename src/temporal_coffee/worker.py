"""Temporal worker — polls the coffee-orders task queue."""

import asyncio
import logging

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from temporal_coffee.activities import brew_coffee, charge_customer, send_receipt
from temporal_coffee.workflows import OrderCoffeeWorkflow

TASK_QUEUE = "coffee-orders"


async def run_worker() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger = logging.getLogger(__name__)

    client = await Client.connect("localhost:7233", data_converter=pydantic_data_converter)
    logger.info("Connected to Temporal — starting worker on queue %r", TASK_QUEUE)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[OrderCoffeeWorkflow],
        activities=[charge_customer, brew_coffee, send_receipt],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
