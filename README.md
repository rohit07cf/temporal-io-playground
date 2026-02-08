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

## How Temporal Works — Complete Flow

The diagram below shows the full lifecycle of a coffee order, from worker
startup through workflow completion. Read it top-to-bottom — each numbered
step happens in sequence.

```
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                          TEMPORAL SERVER (localhost:7233)                   │
 │                                                                            │
 │  Durable execution engine. Persists workflow state, dispatches tasks,      │
 │  manages retries, and routes signals/queries to running workflows.         │
 │                                                                            │
 │  ┌──────────────────────────────────────────────────────────────────────┐  │
 │  │               TASK QUEUE: "coffee-orders"                            │  │
 │  │                                                                      │  │
 │  │  Two types of tasks flow through this queue:                         │  │
 │  │    • Workflow Tasks  — "start/resume this workflow"                   │  │
 │  │    • Activity Tasks  — "execute this activity function"              │  │
 │  └──────────────────────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────────────────┘
          ▲                  │                              ▲         │
          │                  │                              │         │
          │                  ▼                              │         ▼
 ══════════════════════════════════════════════════════════════════════════════

  STEP 1: WORKER STARTS                      STEP 2: CLIENT SUBMITS ORDER
  ════════════════════                        ════════════════════════════

  ┌──────────────────────┐                    ┌─────────────────────────┐
  │     worker.py        │                    │       client.py         │
  │                      │                    │                         │
  │  • Connects to       │                    │  • Connects to server   │
  │    Temporal server   │                    │  • Builds OrderRequest  │
  │  • Registers:        │                    │    (Pydantic model)     │
  │    - OrderCoffee-    │                    │  • Calls start_workflow │
  │      Workflow        │ ──── polls ────►   │    with workflow ID     │
  │    - charge_customer │ ◄── (long poll) ── │    + task queue name    │
  │    - brew_coffee     │                    │  • Gets back a handle   │
  │    - send_receipt    │                    │    to the running       │
  │  • Polls task queue  │                    │    workflow execution   │
  │    "coffee-orders"   │                    │                         │
  │    in a loop         │                    │  Optionally:            │
  │                      │                    │  • --query → get_status │
  │  (Sits idle until    │                    │  • --cancel-after →     │
  │   a task arrives)    │                    │      cancel_order signal│
  └──────────────────────┘                    └─────────────────────────┘

 ══════════════════════════════════════════════════════════════════════════════

  STEP 3: WORKFLOW EXECUTION (inside the worker process)
  ══════════════════════════════════════════════════════

  The server places a Workflow Task on the queue. The worker picks it up
  and runs OrderCoffeeWorkflow.run(req) inside the deterministic sandbox.

  ┌─────────────────────────────────────────────────────────────────────┐
  │                    OrderCoffeeWorkflow.run()                        │
  │                                                                     │
  │  ① Compute price (deterministic — runs in-workflow, not activity)   │
  │     StandardPricingStrategy.price_cents(req) → 525 cents            │
  │                                                                     │
  │  ② Check cancelled flag (from signal)                               │
  │     if self.state.cancelled → return CANCELLED                      │
  │                                                                     │
  │  ③ Schedule charge_customer activity ──────────────────────────┐    │
  │     (workflow suspends here; server persists state)            │    │
  │                                                                │    │
  │  ┌─────────────────────────────────────────────────────────────┘    │
  │  │  Server puts Activity Task on queue → worker picks it up         │
  │  │                                                                  │
  │  │  ┌────────────────────────────────────────────┐                  │
  │  │  │  charge_customer(ChargeInput)               │                  │
  │  │  │    → PaymentService.charge()                │                  │
  │  │  │    → sleep 0.5s, return True                │                  │
  │  │  └────────────────────────────────────────────┘                  │
  │  │  Result sent back to server → workflow resumes                   │
  │  │  self.state.charged = True ✓                                     │
  │  │                                                                  │
  │  ④ Check cancelled flag again                                       │
  │                                                                     │
  │  ⑤ Schedule brew_coffee activity ──────────────────────────────┐    │
  │     (workflow suspends again)                                  │    │
  │                                                                │    │
  │  ┌─────────────────────────────────────────────────────────────┘    │
  │  │  ┌────────────────────────────────────────────┐                  │
  │  │  │  brew_coffee(BrewInput)                     │                  │
  │  │  │    → BrewService.brew()                     │                  │
  │  │  │    → sleep 1.0s                             │                  │
  │  │  │    → 30% chance: FAIL ✗ (RuntimeError)      │                  │
  │  │  └────────────────────────────────────────────┘                  │
  │  │                                                                  │
  │  │  ┌──── RETRY LOOP (handled by Temporal, not your code) ───────┐ │
  │  │  │  RetryPolicy: max 5 attempts, 1s initial, 2x backoff      │ │
  │  │  │                                                            │ │
  │  │  │  Attempt 1: FAIL  → wait 1s                                │ │
  │  │  │  Attempt 2: FAIL  → wait 2s                                │ │
  │  │  │  Attempt 3: OK ✓  → result sent back to server             │ │
  │  │  │                                                            │ │
  │  │  │  (If all 5 fail → exception propagates to workflow         │ │
  │  │  │   → caught by except block → return FAILED)                │ │
  │  │  └────────────────────────────────────────────────────────────┘ │
  │  │  self.state.brewed = True ✓                                     │
  │  │                                                                  │
  │  ⑥ Check cancelled flag again                                       │
  │                                                                     │
  │  ⑦ Schedule send_receipt activity ─────────────────────────────┐    │
  │                                                                │    │
  │  ┌─────────────────────────────────────────────────────────────┘    │
  │  │  ┌────────────────────────────────────────────┐                  │
  │  │  │  send_receipt(ReceiptInput)                  │                  │
  │  │  │    → NotificationService.send_receipt()      │                  │
  │  │  │    → sleep 0.3s, return True                 │                  │
  │  │  └────────────────────────────────────────────┘                  │
  │  │  self.state.receipt_sent = True ✓                                │
  │  │                                                                  │
  │  ⑧ Return OrderResult(status=COMPLETED, ...)                        │
  └─────────────────────────────────────────────────────────────────────┘

 ══════════════════════════════════════════════════════════════════════════════

  STEP 4: CLIENT RECEIVES RESULT
  ══════════════════════════════

  handle.result() unblocks → OrderResult deserialized via pydantic_data_converter

  ┌───────────────────────────────┐
  │  {                            │
  │    "order_id": "123",         │
  │    "status": "COMPLETED",     │
  │    "charged": true,           │
  │    "brewed": true,            │
  │    "receipt_sent": true,      │
  │    "amount_cents": 525        │
  │  }                            │
  └───────────────────────────────┘

 ══════════════════════════════════════════════════════════════════════════════

  SIGNAL & QUERY (can happen at any time while workflow is running)
  ════════════════════════════════════════════════════════════════

  ┌──────────┐    signal: cancel_order     ┌──────────────────────────┐
  │  client   │ ─────────────────────────► │  Temporal Server routes   │
  │           │                            │  signal to workflow       │
  │           │    query: get_status        │  → sets cancelled=True   │
  │           │ ─────────────────────────► │                          │
  │           │ ◄───────────────────────── │  → returns state dict    │
  └──────────┘    (read-only, instant)     └──────────────────────────┘
```

### Key Concepts Illustrated

| Concept | Where it happens | Why it matters |
|---------|-----------------|----------------|
| **Task Queue** | Server-side `"coffee-orders"` | Decouples clients from workers. Multiple workers can poll the same queue for scaling. |
| **Workflow Task** | Server → Worker (step 3) | Tells the worker to run/resume the workflow's deterministic code. |
| **Activity Task** | Server → Worker (steps ③⑤⑦) | Tells the worker to execute one activity function (where side-effects live). |
| **Durable State** | Server persists at each `await` | If the worker crashes mid-brew, the server replays the workflow from the last checkpoint. |
| **Retry Policy** | Configured per-activity in workflow | Temporal handles retry scheduling, backoff, and attempt counting — your code just raises. |
| **Signal** | Client → Server → Workflow | Fire-and-forget message that mutates workflow state (e.g. cancellation). |
| **Query** | Client → Server → Workflow → Client | Synchronous read-only peek at workflow state without affecting execution. |
| **Data Converter** | Client + Worker (both sides) | `pydantic_data_converter` ensures Pydantic models serialize/deserialize correctly in Temporal's JSON payloads. |

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

### 0. Install Temporal CLI

```bash
curl -sSf https://temporal.download/cli.sh | bash
echo 'export PATH="$HOME/.temporalio/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

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
