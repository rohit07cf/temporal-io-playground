"""CLI client — starts a coffee order workflow and optionally queries / cancels it."""

import argparse
import asyncio
import logging

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from temporal_coffee.domain.models import DrinkSize, OrderRequest
from temporal_coffee.workflows import OrderCoffeeWorkflow

TASK_QUEUE = "coffee-orders"


async def run_client(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger = logging.getLogger(__name__)

    client = await Client.connect("localhost:7233", data_converter=pydantic_data_converter)

    req = OrderRequest(order_id=args.order_id, drink=args.drink, size=DrinkSize(args.size))
    workflow_id = f"order-{req.order_id}"

    logger.info("Starting workflow %s", workflow_id)
    handle = await client.start_workflow(
        OrderCoffeeWorkflow.run,
        req,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    if args.query:
        status = await handle.query(OrderCoffeeWorkflow.get_status)
        logger.info("Query result: %s", status)

    if args.cancel_after is not None:
        await asyncio.sleep(args.cancel_after)
        logger.info("Sending cancel signal to %s", workflow_id)
        await handle.signal(OrderCoffeeWorkflow.cancel_order)

    result = await handle.result()
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
