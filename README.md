# Temporal Coffee — Order Workflow Example

A minimal [Temporal IO](https://temporal.io) example in Python demonstrating core workflow concepts with clean OOP design.

## What This Demonstrates

**Temporal concepts:**
- **Workflow orchestration** — sequential activity execution with state tracking
- **Activities** — idempotent units of work with automatic retries
- **Worker** — long-running process polling a task queue
- **Task queue** — `coffee-orders` queue connecting clients to workers
- **Retries & timeouts** — exponential backoff (5 attempts, 1s initial, 2x coefficient)
- **Signal** — cancel a running order mid-flight
- **Query** — inspect workflow state without affecting execution

**OOP / design patterns:**
- **Pydantic v2 models** — typed, validated domain schemas
- **Strategy pattern** — pluggable pricing via `PricingStrategy` protocol
- **Service layer / facade** — `PaymentService`, `BrewService`, `NotificationService`
- **Factory** — `ServiceFactory` for cached service construction

## Architecture

```
                         ┌──────────────────┐
                         │  Temporal Server  │
                         └────────┬─────────┘
                                  │
  client.py ──► [task queue: coffee-orders] ──► worker.py
                                                   │
                                            OrderCoffeeWorkflow
                                                   │
                              ┌────────────────────┼────────────────────┐
                              ▼                    ▼                    ▼
                       charge_customer        brew_coffee         send_receipt
                         (activity)           (activity)           (activity)
                              │                    │                    │
                              ▼                    ▼                    ▼
                       PaymentService         BrewService      NotificationService
```

## File Overview

```
src/temporal_coffee/
├── domain/
│   ├── models.py      # Pydantic v2 models: OrderRequest, OrderState, OrderResult, etc.
│   └── pricing.py     # PricingStrategy protocol + StandardPricingStrategy
├── services/
│   ├── payment.py     # PaymentService — simulates charging
│   ├── brewing.py     # BrewService — simulates brewing (~30% random failure)
│   ├── notify.py      # NotificationService — simulates sending receipts
│   └── factory.py     # ServiceFactory — cached singleton construction
├── activities.py      # Temporal activities (thin wrappers around services)
├── workflows.py       # OrderCoffeeWorkflow with signal + query support
├── worker.py          # Worker entry point — polls coffee-orders queue
└── client.py          # CLI client — starts workflows, supports --query and --cancel-after
```

## Prerequisites

- Python 3.11+
- Temporal dev server ([install guide](https://docs.temporal.io/cli#install))

## Getting Started

### 1. Start the Temporal dev server

```bash
temporal server start-dev
```

This starts the server at `localhost:7233` with a web UI at `http://localhost:8233`.

### 2. Install the project

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Start the worker

```bash
python -m temporal_coffee.worker
```

### 4. Place an order (in a separate terminal)

```bash
python -m temporal_coffee.client --order-id 123 --drink latte --size M
```

### 5. Query workflow status

```bash
python -m temporal_coffee.client --order-id 456 --drink mocha --size L --query
```

### 6. Cancel an order after 1 second

```bash
python -m temporal_coffee.client --order-id 789 --drink espresso --size S --cancel-after 1.0
```

## Example Output

**Worker logs** (showing brew retry after random failure):

```
2025-01-15 10:00:01 [INFO] temporal_coffee.services.payment: Charging order 123 for 525 cents
2025-01-15 10:00:01 [INFO] temporal_coffee.services.payment: Charge successful for order 123
2025-01-15 10:00:02 [INFO] temporal_coffee.services.brewing: Brewing latte (M) for order 123
2025-01-15 10:00:03 [ERROR] temporal_coffee.services.brewing: Brew machine jammed for order 123!
2025-01-15 10:00:04 [INFO] temporal_coffee.services.brewing: Brewing latte (M) for order 123
2025-01-15 10:00:05 [INFO] temporal_coffee.services.brewing: Brew complete for order 123
2025-01-15 10:00:05 [INFO] temporal_coffee.services.notify: Sending receipt for order 123
2025-01-15 10:00:05 [INFO] temporal_coffee.services.notify: Receipt sent for order 123
```

**Client output:**

```json
{
  "order_id": "123",
  "status": "COMPLETED",
  "charged": true,
  "brewed": true,
  "receipt_sent": true,
  "amount_cents": 525
}
```

The `amount_cents` of 525 = 450 (medium base) + 75 (latte surcharge).
