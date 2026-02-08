"""Temporal workflow — OrderCoffeeWorkflow."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_coffee.activities import brew_coffee, charge_customer, send_receipt
    from temporal_coffee.domain.models import (
        BrewInput,
        ChargeInput,
        OrderRequest,
        OrderResult,
        OrderState,
        OrderStatus,
        ReceiptInput,
    )
    from temporal_coffee.domain.pricing import PricingStrategy, StandardPricingStrategy


@workflow.defn
class OrderCoffeeWorkflow:
    """Orchestrates the full lifecycle of a coffee order."""

    def __init__(self) -> None:
        self.state = OrderState()
        self.pricing: PricingStrategy = StandardPricingStrategy()
        self.request: OrderRequest | None = None
        self.amount_cents: int | None = None

    # ── Signal & Query ───────────────────────────────────────────

    @workflow.signal
    async def cancel_order(self) -> None:
        self.state.cancelled = True

    @workflow.query
    def get_status(self) -> dict:
        return {
            "cancelled": self.state.cancelled,
            "charged": self.state.charged,
            "brewed": self.state.brewed,
            "receipt_sent": self.state.receipt_sent,
            "amount_cents": self.amount_cents,
            "order_id": self.request.order_id if self.request else None,
        }

    # ── Helpers ──────────────────────────────────────────────────

    def _result(self, status: OrderStatus) -> OrderResult:
        return OrderResult(
            order_id=self.request.order_id if self.request else "",
            status=status,
            charged=self.state.charged,
            brewed=self.state.brewed,
            receipt_sent=self.state.receipt_sent,
            amount_cents=self.amount_cents or 0,
        )

    # ── Run ──────────────────────────────────────────────────────

    @workflow.run
    async def run(self, req: OrderRequest) -> OrderResult:
        self.request = req
        self.amount_cents = self.pricing.price_cents(req)

        retry_policy = RetryPolicy(
            maximum_attempts=5,
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
        )
        activity_opts = {
            "start_to_close_timeout": timedelta(seconds=10),
            "retry_policy": retry_policy,
        }

        workflow.logger.info(
            "Starting order %s — %s (%s) for %d cents",
            req.order_id,
            req.drink,
            req.size.value,
            self.amount_cents,
        )

        try:
            # Step 1: Charge
            if self.state.cancelled:
                return self._result(OrderStatus.CANCELLED)
            await workflow.execute_activity(
                charge_customer,
                ChargeInput(order_id=req.order_id, amount_cents=self.amount_cents),
                **activity_opts,
            )
            self.state.charged = True

            # Step 2: Brew
            if self.state.cancelled:
                return self._result(OrderStatus.CANCELLED)
            await workflow.execute_activity(
                brew_coffee,
                BrewInput(order_id=req.order_id, drink=req.drink, size=req.size),
                **activity_opts,
            )
            self.state.brewed = True

            # Step 3: Receipt
            if self.state.cancelled:
                return self._result(OrderStatus.CANCELLED)
            await workflow.execute_activity(
                send_receipt,
                ReceiptInput(order_id=req.order_id),
                **activity_opts,
            )
            self.state.receipt_sent = True

        except Exception:
            workflow.logger.exception("Order %s failed", req.order_id)
            return self._result(OrderStatus.FAILED)

        workflow.logger.info("Order %s completed successfully", req.order_id)
        return self._result(OrderStatus.COMPLETED)
