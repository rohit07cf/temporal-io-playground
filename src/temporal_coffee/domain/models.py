"""
Domain models for the coffee ordering workflow.

All models use Pydantic v2 BaseModel for automatic validation, serialization,
and deserialization. Temporal transmits workflow/activity inputs and outputs as
JSON payloads — Pydantic models serialize cleanly via the pydantic_data_converter
configured on both the client and the worker.

Enums inherit from (str, Enum) so they serialize as plain strings in JSON
(e.g. "M" instead of {"value": "M"}).
"""

from enum import Enum

from pydantic import BaseModel, Field


class DrinkSize(str, Enum):
    """Available drink sizes — mapped to base prices in pricing.py."""

    S = "S"  # Small  — 300 cents
    M = "M"  # Medium — 450 cents
    L = "L"  # Large  — 600 cents


class OrderStatus(str, Enum):
    """Terminal status of a coffee order workflow."""

    COMPLETED = "COMPLETED"   # All activities succeeded
    FAILED = "FAILED"         # An activity failed after exhausting retries
    CANCELLED = "CANCELLED"   # A cancel signal was received before completion


# ── Workflow input / output ──────────────────────────────────────────


class OrderRequest(BaseModel):
    """Input to the coffee-order workflow.

    Passed from the client to `OrderCoffeeWorkflow.run()` via Temporal.
    """

    order_id: str = Field(..., min_length=1)  # Unique identifier for the order
    drink: str = Field(..., min_length=1)     # Drink name, e.g. "latte", "mocha"
    size: DrinkSize                           # Desired drink size


class OrderState(BaseModel):
    """Mutable state tracked inside the workflow execution.

    Updated after each activity completes. Queryable via the `get_status`
    query handler on the workflow.
    """

    charged: bool = False       # True after charge_customer activity succeeds
    brewed: bool = False        # True after brew_coffee activity succeeds
    receipt_sent: bool = False  # True after send_receipt activity succeeds
    cancelled: bool = False     # True when cancel_order signal is received


class OrderResult(BaseModel):
    """Final result returned by the workflow to the client.

    Contains the terminal status and a snapshot of which steps completed.
    """

    order_id: str
    status: OrderStatus
    charged: bool
    brewed: bool
    receipt_sent: bool
    amount_cents: int  # Computed price in cents


# ── Activity payload models ──────────────────────────────────────────
# Each activity takes a single Pydantic model as input. This keeps the
# activity interface clean and ensures payloads are validated on both
# the sending (workflow) and receiving (activity) side.


class ChargeInput(BaseModel):
    """Payload for the charge_customer activity."""

    order_id: str
    amount_cents: int = Field(..., ge=0)  # Must be non-negative


class BrewInput(BaseModel):
    """Payload for the brew_coffee activity."""

    order_id: str
    drink: str
    size: DrinkSize


class ReceiptInput(BaseModel):
    """Payload for the send_receipt activity."""

    order_id: str
