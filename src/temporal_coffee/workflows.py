"""
Temporal workflow — OrderCoffeeWorkflow.

A Temporal **workflow** is a durable, fault-tolerant function that orchestrates
the execution of activities. The Temporal server persists its state at every
`await` point, so if the worker crashes the workflow automatically resumes
from the last checkpoint — no manual recovery needed.

Key constraints inside a workflow:
  - Must be **deterministic**: no I/O, no randomness, no system clock.
    (Use activities for side-effects; use `workflow.now()` for time.)
  - Use `workflow.execute_activity(...)` to dispatch work to activities.
  - Use `workflow.logger` instead of the stdlib `logging` module.
"""

from datetime import timedelta

# `workflow` is the core Temporal SDK module for defining workflows.
# It provides decorators (@workflow.defn, @workflow.run, @workflow.signal,
# @workflow.query) and helpers (execute_activity, logger, now, etc.).
from temporalio import workflow

# RetryPolicy configures how Temporal retries failed activity executions.
# It is attached per-activity when calling `workflow.execute_activity(...)`.
from temporalio.common import RetryPolicy

# ── Sandbox-safe imports ─────────────────────────────────────────────
# Temporal runs workflows inside a restricted sandbox that intercepts imports
# to enforce determinism (e.g. blocking `random`, `os`, `datetime.now`).
# Pydantic and our own modules use constructs the sandbox would flag, so we
# wrap them with `workflow.unsafe.imports_passed_through()` to bypass the
# sandbox's import interception for these specific modules.
# This is safe because the imported code is only used for data modelling and
# deterministic computation — no side-effects happen at import time.
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


# @workflow.defn — marks this class as a Temporal workflow definition.
# The Temporal worker will register it and the server can schedule executions.
@workflow.defn
class OrderCoffeeWorkflow:
    """Orchestrates the full lifecycle of a coffee order.

    Execution flow:
        1. Compute price (deterministic, in-workflow)
        2. charge_customer activity  → PaymentService
        3. brew_coffee activity      → BrewService  (may fail & retry)
        4. send_receipt activity     → NotificationService

    Supports:
        - **Signal** `cancel_order`: external callers can cancel mid-flight.
        - **Query** `get_status`: external callers can inspect state without
          affecting execution.
    """

    def __init__(self) -> None:
        # Workflow instance state — Temporal persists this across replays.
        self.state = OrderState()
        # Strategy pattern: swap in a different pricing strategy if needed.
        self.pricing: PricingStrategy = StandardPricingStrategy()
        self.request: OrderRequest | None = None
        self.amount_cents: int | None = None

    # ── Signal ────────────────────────────────────────────────────
    # A **signal** is an async message sent to a running workflow from the
    # outside (e.g., a client or another workflow). It mutates workflow state
    # but does NOT return a value to the sender. The workflow checks the
    # `cancelled` flag before each activity to decide whether to short-circuit.

    @workflow.signal
    async def cancel_order(self) -> None:
        self.state.cancelled = True

    # ── Query ─────────────────────────────────────────────────────
    # A **query** is a synchronous, read-only inspection of workflow state.
    # It MUST NOT mutate state or perform side-effects. The caller receives
    # the return value immediately without affecting workflow progress.

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
        """Build an OrderResult snapshot from current state."""
        return OrderResult(
            order_id=self.request.order_id if self.request else "",
            status=status,
            charged=self.state.charged,
            brewed=self.state.brewed,
            receipt_sent=self.state.receipt_sent,
            amount_cents=self.amount_cents or 0,
        )

    # ── Run (main workflow logic) ────────────────────────────────
    # @workflow.run — marks the entry-point method. Exactly one method per
    # workflow class must have this decorator. Its signature defines the
    # workflow's input type(s) and return type.

    @workflow.run
    async def run(self, req: OrderRequest) -> OrderResult:
        self.request = req
        # Pricing is deterministic (no I/O), so it runs directly in the
        # workflow — no need for an activity.
        self.amount_cents = self.pricing.price_cents(req)

        # ── Retry policy ─────────────────────────────────────────
        # Temporal automatically retries failed activities according to this
        # policy. With these settings, brew_coffee (which randomly fails ~30%
        # of the time) will retry up to 5 times with exponential backoff:
        #   attempt 1 → wait 1s → attempt 2 → wait 2s → attempt 3 → wait 4s → ...
        retry_policy = RetryPolicy(
            maximum_attempts=5,            # give up after 5 tries
            initial_interval=timedelta(seconds=1),  # first retry delay
            backoff_coefficient=2.0,       # double the delay each retry
        )

        # ── Activity options ─────────────────────────────────────
        # start_to_close_timeout: max wall-clock time for a single activity
        # attempt. If the activity doesn't complete within this window,
        # Temporal marks it as timed out and (if retries remain) retries it.
        activity_opts = {
            "start_to_close_timeout": timedelta(seconds=10),
            "retry_policy": retry_policy,
        }

        # workflow.logger is a sandbox-safe logger provided by Temporal.
        # Never use stdlib `logging` directly inside a workflow.
        workflow.logger.info(
            "Starting order %s — %s (%s) for %d cents",
            req.order_id,
            req.drink,
            req.size.value,
            self.amount_cents,
        )

        try:
            # Step 1: Charge the customer
            # Check cancellation flag before each activity so we can
            # short-circuit early if a cancel signal arrived.
            if self.state.cancelled:
                return self._result(OrderStatus.CANCELLED)
            # workflow.execute_activity dispatches the activity to the worker's
            # activity task executor. The workflow suspends here until the
            # activity completes (or fails after all retries).
            await workflow.execute_activity(
                charge_customer,
                ChargeInput(order_id=req.order_id, amount_cents=self.amount_cents),
                **activity_opts,
            )
            self.state.charged = True

            # Step 2: Brew the coffee
            if self.state.cancelled:
                return self._result(OrderStatus.CANCELLED)
            # brew_coffee may raise RuntimeError ~30% of the time.
            # Temporal will automatically retry it per the retry_policy above.
            await workflow.execute_activity(
                brew_coffee,
                BrewInput(order_id=req.order_id, drink=req.drink, size=req.size),
                **activity_opts,
            )
            self.state.brewed = True

            # Step 3: Send receipt
            if self.state.cancelled:
                return self._result(OrderStatus.CANCELLED)
            await workflow.execute_activity(
                send_receipt,
                ReceiptInput(order_id=req.order_id),
                **activity_opts,
            )
            self.state.receipt_sent = True

        except Exception:
            # If an activity fails after exhausting all retries, the exception
            # propagates here. We catch it and return a FAILED result so the
            # workflow completes gracefully instead of being marked as "failed"
            # by the Temporal server.
            workflow.logger.exception("Order %s failed", req.order_id)
            return self._result(OrderStatus.FAILED)

        workflow.logger.info("Order %s completed successfully", req.order_id)
        return self._result(OrderStatus.COMPLETED)
