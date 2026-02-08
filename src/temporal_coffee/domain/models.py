"""Domain models for the coffee ordering workflow."""

from enum import Enum

from pydantic import BaseModel, Field


class DrinkSize(str, Enum):
    """Available drink sizes."""

    S = "S"
    M = "M"
    L = "L"


class OrderStatus(str, Enum):
    """Terminal status of a coffee order."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ── Workflow input / output ──────────────────────────────────────────


class OrderRequest(BaseModel):
    """Input to the coffee-order workflow."""

    order_id: str = Field(..., min_length=1)
    drink: str = Field(..., min_length=1)
    size: DrinkSize


class OrderState(BaseModel):
    """Mutable state tracked inside the workflow execution."""

    charged: bool = False
    brewed: bool = False
    receipt_sent: bool = False
    cancelled: bool = False


class OrderResult(BaseModel):
    """Final result returned by the workflow."""

    order_id: str
    status: OrderStatus
    charged: bool
    brewed: bool
    receipt_sent: bool
    amount_cents: int


# ── Activity payload models ──────────────────────────────────────────


class ChargeInput(BaseModel):
    """Payload for the charge_customer activity."""

    order_id: str
    amount_cents: int = Field(..., ge=0)


class BrewInput(BaseModel):
    """Payload for the brew_coffee activity."""

    order_id: str
    drink: str
    size: DrinkSize


class ReceiptInput(BaseModel):
    """Payload for the send_receipt activity."""

    order_id: str
