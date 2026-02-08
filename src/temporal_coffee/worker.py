"""
Temporal worker — polls the "coffee-orders" task queue.

A **worker** is a long-running process that connects to the Temporal server
and polls a **task queue** for work. When the server has a workflow task or
activity task ready, it dispatches it to a worker listening on the matching
task queue.

The worker must register:
  - **Workflows** it can execute (here: OrderCoffeeWorkflow)
  - **Activities** it can run (here: charge_customer, brew_coffee, send_receipt)

Multiple workers can poll the same task queue for horizontal scaling.
Temporal guarantees each task is delivered to exactly one worker.

Run with:
    python -m temporal_coffee.worker
"""

import asyncio
import logging

# Client connects to the Temporal server (default: localhost:7233).
from temporalio.client import Client

# pydantic_data_converter enables the Temporal SDK to serialize/deserialize
# Pydantic v2 models when passing workflow inputs, activity inputs, and
# workflow results across the wire. Without this, Pydantic models would fail
# to round-trip through Temporal's JSON payload converter.
# IMPORTANT: The same data_converter must be used on both the worker AND the
# client, otherwise deserialization will fail.
from temporalio.contrib.pydantic import pydantic_data_converter

# Worker is the main event loop that polls the Temporal server for tasks.
from temporalio.worker import Worker

from temporal_coffee.activities import brew_coffee, charge_customer, send_receipt
from temporal_coffee.workflows import OrderCoffeeWorkflow

# Task queue name — a logical queue that connects clients to workers.
# The client specifies this when starting a workflow, and the worker
# specifies it when polling. They must match for work to be routed.
TASK_QUEUE = "coffee-orders"


async def run_worker() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger = logging.getLogger(__name__)

    # Connect to the Temporal server with the Pydantic-aware data converter.
    client = await Client.connect("localhost:7233", data_converter=pydantic_data_converter)
    logger.info("Connected to Temporal — starting worker on queue %r", TASK_QUEUE)

    # Create and start the worker. It will:
    #   1. Poll the "coffee-orders" task queue for workflow and activity tasks.
    #   2. Execute OrderCoffeeWorkflow when a new workflow execution is started.
    #   3. Execute activity functions when the workflow dispatches activity tasks.
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[OrderCoffeeWorkflow],
        activities=[charge_customer, brew_coffee, send_receipt],
    )
    # worker.run() blocks until the worker is shut down (e.g., via Ctrl+C).
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
