"""
CLI client — starts a coffee order workflow and optionally queries / cancels it.

This module acts as the **workflow starter**. It connects to the Temporal
server, submits a new workflow execution request, and (optionally) interacts
with the running workflow via queries and signals.

Usage:
    # Start a basic order:
    python -m temporal_coffee.client --order-id 123 --drink latte --size M

    # Start + immediately query the workflow's current state:
    python -m temporal_coffee.client --order-id 456 --drink mocha --size L --query

    # Start + cancel the order after 1 second:
    python -m temporal_coffee.client --order-id 789 --drink espresso --size S --cancel-after 1.0
"""

import argparse
import asyncio
import logging

# Client is the Temporal SDK's entry point for interacting with the server.
# It can start workflows, send signals, run queries, and fetch results.
from temporalio.client import Client

# Must match the data_converter used by the worker — see worker.py comments.
from temporalio.contrib.pydantic import pydantic_data_converter

from temporal_coffee.domain.models import DrinkSize, OrderRequest
from temporal_coffee.workflows import OrderCoffeeWorkflow

# Must match the task queue the worker is polling — see worker.py.
TASK_QUEUE = "coffee-orders"


async def run_client(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger = logging.getLogger(__name__)

    # Connect to Temporal with the Pydantic data converter so that
    # OrderRequest and OrderResult serialize/deserialize correctly.
    client = await Client.connect("localhost:7233", data_converter=pydantic_data_converter)

    req = OrderRequest(order_id=args.order_id, drink=args.drink, size=DrinkSize(args.size))
    workflow_id = f"order-{req.order_id}"

    logger.info("Starting workflow %s", workflow_id)

    # start_workflow sends an execution request to the Temporal server.
    # The server enqueues a task on the "coffee-orders" task queue,
    # and a worker picks it up to run OrderCoffeeWorkflow.run(req).
    # `handle` is a lightweight reference to the running workflow.
    handle = await client.start_workflow(
        OrderCoffeeWorkflow.run,   # type-safe reference to the workflow's run method
        req,                       # workflow input (serialized via pydantic_data_converter)
        id=workflow_id,            # unique workflow ID (prevents duplicate orders)
        task_queue=TASK_QUEUE,     # routes to workers polling this queue
    )

    # Query: read-only inspection of workflow state. The workflow's
    # @workflow.query method (get_status) is invoked on the server side
    # and its return value comes back here. Does NOT affect execution.
    if args.query:
        status = await handle.query(OrderCoffeeWorkflow.get_status)
        logger.info("Query result: %s", status)

    # Signal: async message sent to a running workflow. The workflow's
    # @workflow.signal method (cancel_order) is invoked, setting the
    # `cancelled` flag. The workflow checks this flag before each activity.
    if args.cancel_after is not None:
        await asyncio.sleep(args.cancel_after)
        logger.info("Sending cancel signal to %s", workflow_id)
        await handle.signal(OrderCoffeeWorkflow.cancel_order)

    # Block until the workflow completes and return the OrderResult.
    # The result is deserialized back into a Pydantic model automatically.
    result = await handle.result()
    # Pretty-print the result as JSON using Pydantic's built-in serializer.
    print(result.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Order a coffee via Temporal")
    parser.add_argument("--order-id", required=True, help="Unique order identifier")
    parser.add_argument("--drink", required=True, help="Drink name, e.g. latte")
    parser.add_argument("--size", required=True, choices=["S", "M", "L"], help="Drink size")
    parser.add_argument("--query", action="store_true", help="Query workflow status once after starting")
    parser.add_argument("--cancel-after", type=float, default=None, help="Seconds to wait before sending cancel signal")
    asyncio.run(run_client(parser.parse_args()))


if __name__ == "__main__":
    main()
