# Payment Event Ingestion & Reconciliation Service

A production-minded backend service for payment event ingestion and reconciliation, built with **FastAPI**, **MySQL**, **SQLAlchemy ORM**, and **Alembic** migrations.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Technology Choices](#technology-choices)
- [Database Schema](#database-schema)
- [Idempotency Strategy](#idempotency-strategy)
- [State Machine](#state-machine)
- [Reconciliation Logic](#reconciliation-logic)
- [API Documentation](#api-documentation)
- [Quick Start](#quick-start)
- [Seed Data](#seed-data)
- [Running Tests](#running-tests)
- [Deployment](#deployment)
- [Assumptions & Tradeoffs](#assumptions--tradeoffs)

---

## Architecture Overview

```
app/
├── api/v1/endpoints/     # HTTP layer — request/response handling
├── services/             # Business logic — state machine, orchestration
├── repositories/         # Data access — SQL queries, persistence
├── models/               # SQLAlchemy ORM models
├── schemas/              # Pydantic request/response schemas
├── enums/                # Enums and state machine definitions
├── core/                 # Config and exceptions
├── middleware/           # Global error handlers
├── dependencies/         # FastAPI dependency injection
tests/                    # pytest test suite (MySQL-backed)
scripts/                  # Seed data generator
alembic/                  # Database migrations
```

**Pattern**: Endpoint → Service → Repository. Each layer has a single responsibility:
- **Endpoints** handle HTTP concerns (validation, status codes, docs)
- **Services** own business logic (state transitions, orchestration)
- **Repositories** own SQL (queries, persistence, aggregation)

---

## Technology Choices

| Technology | Reason |
|---|---|
| **FastAPI** | Async-ready, auto-generated OpenAPI docs, Pydantic integration, dependency injection |
| **MySQL** | Strong ACID compliance, mature ecosystem, excellent for indexed queries and aggregation |
| **SQLAlchemy 2.0** | Industry-standard ORM with excellent query builder for complex aggregation |
| **Alembic** | Reliable schema migration tool, integrates seamlessly with SQLAlchemy |
| **Pydantic v2** | Fast validation, clean schema definitions, native FastAPI integration |
| **Docker Compose** | Reproducible local setup with MySQL + app in one command |

---

## Database Schema

### Tables

**`merchants`** — Reference table for merchant data
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | Merchant identifier |
| name | VARCHAR(255) | Display name |
| created_at | DATETIME | Auto-set |

**`transactions`** — Derived current state of each transaction (dual-status model)
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(100) PK | Transaction ID from events |
| merchant_id | VARCHAR(36) FK | Indexed |
| amount | DECIMAL(12,2) | Transaction amount |
| currency | VARCHAR(3) | Default: INR |
| payment_status | ENUM(initiated, processed, failed) | Current payment state |
| settlement_status | ENUM(pending, settled, not_applicable) | Current settlement state |
| created_at | DATETIME | First event time |
| updated_at | DATETIME | Last state change |

**`payment_events`** — Append-only audit log of all ingested events
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | Surrogate key |
| event_id | VARCHAR(100) UNIQUE | Idempotency key |
| transaction_id | VARCHAR(100) FK | Indexed |
| event_type | ENUM | Event type |
| amount | DECIMAL(12,2) | Event amount |
| timestamp | DATETIME | Event occurrence time |
| raw_payload | JSON | Original event for audit |
| created_at | DATETIME | Insertion time |

### Indexes
- Individual: `merchant_id`, `payment_status`, `settlement_status`, `created_at`
- Composite: `(merchant_id, payment_status)`, `(merchant_id, settlement_status)`, `(payment_status, settlement_status, updated_at)`
- Unique: `event_id` on payment_events

### Design Rationale
The **dual-status model** (`payment_status` + `settlement_status`) on `transactions` enables clean discrepancy detection via SQL WHERE clauses. The `payment_events` table preserves full history (event-sourcing-lite), while `transactions` holds derived current state.

---

## Idempotency Strategy

1. Every event has a unique `event_id`
2. On `POST /events`, we first check if `event_id` exists in `payment_events`
3. If **duplicate**: return `200` with `is_duplicate: true` — no state change
4. If **new**: persist event, apply state transition, return `201`
5. Events are **always persisted** in `payment_events` regardless of whether they trigger a state change — the audit log is append-only

This ensures:
- Safe retries (same event_id → same response)
- No data corruption from duplicates
- Complete audit trail

---

## State Machine

| Current State | Event | New payment_status | New settlement_status |
|---|---|---|---|
| _(new)_ | payment_initiated | initiated | pending |
| initiated | payment_processed | processed | pending |
| initiated | payment_failed | failed | not_applicable |
| processed | settled | processed | settled |
| processed | payment_failed | failed | not_applicable |

**Terminal states** (no further transitions):
- `(failed, not_applicable)` — payment failed permanently
- `(processed, settled)` — fully settled

**Out-of-order events**: If an event doesn't match the current state, it is still **persisted for audit** but the transaction state is **not modified**. A warning message is included in the response.

---

## Reconciliation Logic

### Summary (`GET /api/v1/reconciliation/summary`)
SQL-driven aggregation with flexible grouping:
- `group_by=merchant` — GROUP BY merchant_id
- `group_by=date` — GROUP BY DATE(created_at)
- `group_by=status` — GROUP BY payment_status:settlement_status

Returns per-group breakdowns and overall totals with settlement rate.

### Discrepancy Rules (`GET /api/v1/reconciliation/discrepancies`)

| # | Type | Condition | Description |
|---|---|---|---|
| 1 | `unsettled_processed` | payment=processed, settlement=pending, stale | Payment processed but not settled within threshold |
| 2 | `invalid_settlement` | payment=failed, settlement=settled | Settlement recorded for a failed payment |
| 3 | `premature_settlement` | payment=initiated, settlement=settled | Settlement without payment being processed |
| 4 | `stale_initiated` | payment=initiated, settlement=pending, stale | Initiated but no progress within threshold |
| 5 | `duplicate_conflict` | Multiple events of same type per transaction | Conflicting duplicate events detected |

**Staleness threshold**: Configurable via `stale_after_hours` query parameter (default: **24 hours**, max: 8760). Rules 1 and 4 use this threshold. Rules 2 and 3 are absolute invariant violations (always flagged).

---

## API Documentation

### `POST /api/v1/events`
Ingest a payment lifecycle event (idempotent).

**Request:**
```json
{
  "event_id": "evt_001",
  "event_type": "payment_initiated",
  "transaction_id": "txn_001",
  "merchant_id": "merchant_A",
  "merchant_name": "Acme Electronics",
  "amount": 1500.00,
  "currency": "INR",
  "timestamp": "2026-04-20T10:30:00Z"
}
```

**Response (201):** New event accepted
**Response (200):** Duplicate event (idempotent)
**Response (422):** Validation error

### `GET /api/v1/transactions`
List transactions with filtering, pagination, sorting.

**Query params:** `merchant_id`, `payment_status`, `settlement_status`, `date_from`, `date_to`, `sort_by`, `sort_order`, `page`, `page_size`

### `GET /api/v1/transactions/{transaction_id}`
Full transaction detail with event history.

### `GET /api/v1/reconciliation/summary`
Aggregated reconciliation summary.

**Query params:** `group_by` (merchant|date|status), `merchant_id`, `date_from`, `date_to`

### `GET /api/v1/reconciliation/discrepancies`
Detect reconciliation discrepancies.

**Query params:** `stale_after_hours`, `merchant_id`, `discrepancy_type`, `page`, `page_size`

### `GET /api/v1/health`
Health check with database connectivity status.

**Interactive docs:** `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`

---

## Quick Start

### Prerequisites
- Docker and Docker Compose

### 1. Clone and Start

```bash
git clone <repository-url>
cd payment-reconciliation-service

# Start all services (MySQL + App + Adminer)
docker-compose up -d --build
```

This will:
- Start MySQL 8.0 with both `payment_db` and `payment_test_db`
- Run Alembic migrations automatically
- Start the FastAPI server (mapped to port 5005 externally)

### 2. Verify

```bash
curl http://localhost:5005/api/v1/health
```

### 3. Explore

- **Swagger UI:** http://localhost:5005/docs
- **ReDoc:** http://localhost:5005/redoc
- **Adminer (DB UI):** http://localhost:8080

### 4. Seed Sample Data

If you have the `sample_events.json` file provided in the assignment, you can load it directly into your database:

```bash
# Load events from the provided JSON file
python scripts/load_json.py sample_events.json
```

Alternatively, if you want to generate entirely new realistic mock data (10,000+ events):

```bash
# Generate and load new events via API
docker-compose exec app python -m scripts.seed_data --mode api
```

### Migration Commands

```bash
# Run migrations
docker-compose exec app alembic upgrade head

# Rollback one step
docker-compose exec app alembic downgrade -1

# View migration history
docker-compose exec app alembic history
```

---

## Seed Data

The seed script generates **10,000+ events** across **5 merchants** with realistic distribution:

| Scenario | Percentage | Description |
|---|---|---|
| Full lifecycle | ~60% | initiated → processed → settled |
| Failed | ~15% | initiated → failed |
| Unsettled processed | ~10% | initiated → processed (never settled) |
| Duplicate events | ~5% | Same event_id submitted twice |
| Conflicting states | ~5% | Invalid settlements, premature settlement |
| Stale initiated | ~5% | Initiated with no follow-up |

This ensures all discrepancy types are represented in the test data.

---

## Running Tests

Tests run against a **dedicated MySQL test database** (`payment_test_db`) for full SQL behavior parity with production. Each test uses transactional isolation (rollback after completion).

### Prerequisites
Ensure Docker Compose is running (MySQL must be accessible):

```bash
docker-compose up -d
```

### Run Tests

```bash
# Run all tests inside the Docker container
docker-compose exec app pytest tests/ -v

# Run specific test file
docker-compose exec app pytest tests/test_events.py -v

# Run with coverage
docker-compose exec app pytest tests/ -v --tb=short
```

### Test Coverage

| Area | Tests |
|---|---|
| Event ingestion | Valid event, duplicate handling, idempotency preservation |
| State transitions | Full lifecycle, failed, terminal state protection |
| Validation | Missing fields, invalid event_type, negative amount |
| Transaction listing | Merchant filter, status filter, date range, pagination, sorting |
| Transaction detail | Event history, 404 handling, merchant name inclusion |
| Reconciliation summary | Group by merchant/date/status, merchant filter, totals |
| Discrepancies | Detection, type filtering, configurable threshold, validation |

---

## Deployment

### Docker (Recommended)

The app is deployment-ready with Docker. For cloud platforms:

**Render / Railway:**
1. Push to GitHub
2. Connect repository
3. Set environment variables from `.env.example`
4. Deploy — migrations run automatically via entrypoint

**AWS ECS / Fly.io:**
1. Build: `docker build -t payment-service .`
2. Push to container registry
3. Deploy with environment variables configured
4. Ensure MySQL instance is accessible

### Environment Variables

See `.env.example` for all configuration keys. Key variables:

| Variable | Description | Default |
|---|---|---|
| MYSQL_HOST | MySQL server hostname | db |
| MYSQL_PORT | MySQL server port | 3306 |
| MYSQL_DATABASE | Application database name | payment_db |
| MYSQL_USER | Database user | payment_user |
| MYSQL_PASSWORD | Database password | _(set securely)_ |
| DEFAULT_STALE_AFTER_HOURS | Default staleness threshold | 24 |
| CORS_ORIGINS | Allowed CORS origins | * |

---

## Assumptions & Tradeoffs

### Assumptions
1. **Event ordering**: Events may arrive out of order. The state machine applies transitions based on current state, not event timestamp order.
2. **Single currency per transaction**: All events for a transaction share the same amount and currency.
3. **Merchant data**: Merchant name may be updated by later events (upsert behavior).
4. **Staleness**: The 24-hour default threshold works for demonstration purposes and is configurable per request.

### Tradeoffs
1. **Dual-status model vs. event replay**: We maintain `payment_status` and `settlement_status` on the transaction for O(1) reads and efficient SQL aggregation, rather than replaying events on every query. This trades storage for read performance.
2. **In-memory pagination for discrepancies**: Discrepancy results are paginated in Python after SQL queries. For very large datasets, this could be moved to a UNION ALL SQL approach.
3. **Synchronous processing**: Events are processed synchronously. For high-throughput production, a message queue (RabbitMQ/Kafka) would decouple ingestion from processing.
4. **No authentication**: Omitted for assignment scope. Production would add JWT/API key auth.

### What I'd Improve With More Time
1. **Background event processing** via Celery/RQ for async ingestion
2. **Rate limiting** on the events endpoint
3. **Caching** for reconciliation summary with Redis
4. **Webhook notifications** for discrepancy alerts
5. **Batch event ingestion** endpoint for bulk import
6. **More granular discrepancy rules** with configurable severity levels
7. **Database connection pooling** tuning based on load testing
8. **CI/CD pipeline** with GitHub Actions
9. **Structured JSON logging** with correlation IDs for request tracing

---

## Postman Collection

Import `postman_collection.json` into Postman. The collection includes:
- All 5 API endpoints
- Normal flow examples
- Edge cases (duplicates, 404, validation errors)
- Reconciliation with different groupings and thresholds

Set the `base_url` variable to your server address (e.g., `https://jarviss.online` or `http://localhost:5005`).
