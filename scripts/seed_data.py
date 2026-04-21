"""
Seed data generator — creates 10,000+ realistic payment events across 5 merchants.

Generates a mix of:
- ~60% successful full-lifecycle transactions (initiated → processed → settled)
- ~15% failed transactions (initiated → failed)
- ~10% processed but unsettled (discrepancy: unsettled_processed)
- ~5% duplicate events (idempotency test)
- ~5% conflicting states (settled+failed, premature settlement)
- ~5% stale initiated (no further progress)

Usage:
    python -m scripts.seed_data
    # or from Docker:
    docker-compose exec app python -m scripts.seed_data
"""

import sys
import os
import uuid
import random
import json
from datetime import datetime, timedelta
from decimal import Decimal

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.models.payment_event import PaymentEvent
from app.enums.status import PaymentStatus, SettlementStatus, EventType


# --- Configuration ---
MERCHANTS = [
    {"id": "merchant_A", "name": "Acme Electronics"},
    {"id": "merchant_B", "name": "Global Payments Corp"},
    {"id": "merchant_C", "name": "QuickPay Solutions"},
    {"id": "merchant_D", "name": "Metro Retail Group"},
    {"id": "merchant_E", "name": "CloudCommerce Ltd"},
]

NUM_TRANSACTIONS = 3500
BASE_DATE = datetime(2026, 3, 1, 0, 0, 0)
DATE_RANGE_DAYS = 45

# Distribution weights
SCENARIO_WEIGHTS = {
    "full_lifecycle": 60,       # initiated → processed → settled
    "failed": 15,               # initiated → failed
    "unsettled_processed": 10,  # initiated → processed (never settled)
    "duplicate_events": 5,      # duplicated event_ids
    "conflicting": 5,           # invalid states (settled+failed, premature)
    "stale_initiated": 5,       # initiated, no further events
}


def random_amount() -> Decimal:
    """Generate a realistic transaction amount."""
    return Decimal(str(round(random.uniform(50, 50000), 2)))


def random_timestamp(base: datetime, offset_hours_max: int = 48) -> datetime:
    """Generate a timestamp within offset from base."""
    offset = timedelta(
        hours=random.randint(0, offset_hours_max),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return base + offset


def generate_events():
    """Generate all events according to scenario distribution."""
    events = []
    transaction_count = 0
    event_count = 0

    # Build scenario list
    scenarios = []
    for scenario, weight in SCENARIO_WEIGHTS.items():
        count = int(NUM_TRANSACTIONS * weight / 100)
        scenarios.extend([scenario] * count)
    random.shuffle(scenarios)

    for i, scenario in enumerate(scenarios):
        txn_id = f"txn_{i+1:05d}"
        merchant = random.choice(MERCHANTS)
        amount = random_amount()
        day_offset = random.randint(0, DATE_RANGE_DAYS)
        base_time = BASE_DATE + timedelta(days=day_offset)
        transaction_count += 1

        if scenario == "full_lifecycle":
            # initiated → processed → settled
            t1 = random_timestamp(base_time, 1)
            t2 = random_timestamp(t1, 4)
            t3 = random_timestamp(t2, 24)
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_INITIATED, amount, t1))
            event_count += 1
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_PROCESSED, amount, t2))
            event_count += 1
            events.append(_make_event(event_count, txn_id, merchant, EventType.SETTLED, amount, t3))
            event_count += 1

        elif scenario == "failed":
            # initiated → failed
            t1 = random_timestamp(base_time, 1)
            t2 = random_timestamp(t1, 2)
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_INITIATED, amount, t1))
            event_count += 1
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_FAILED, amount, t2))
            event_count += 1

        elif scenario == "unsettled_processed":
            # initiated → processed (but never settled — discrepancy)
            t1 = random_timestamp(base_time, 1)
            t2 = random_timestamp(t1, 4)
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_INITIATED, amount, t1))
            event_count += 1
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_PROCESSED, amount, t2))
            event_count += 1

        elif scenario == "duplicate_events":
            # Full lifecycle + duplicate initiated event
            t1 = random_timestamp(base_time, 1)
            t2 = random_timestamp(t1, 4)
            t3 = random_timestamp(t2, 24)
            eid = f"evt_{event_count:06d}"
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_INITIATED, amount, t1))
            event_count += 1
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_PROCESSED, amount, t2))
            event_count += 1
            events.append(_make_event(event_count, txn_id, merchant, EventType.SETTLED, amount, t3))
            event_count += 1
            # Duplicate: re-use the first event_id
            events.append({
                "event_id": eid,
                "event_type": EventType.PAYMENT_INITIATED.value,
                "transaction_id": txn_id,
                "merchant_id": merchant["id"],
                "merchant_name": merchant["name"],
                "amount": float(amount),
                "currency": "INR",
                "timestamp": t1.isoformat(),
                "_is_duplicate": True,
            })
            event_count += 1

        elif scenario == "conflicting":
            # Create conflicting states:
            # Half: settled event for failed payment
            # Half: settlement without processing (premature)
            if random.random() < 0.5:
                # Failed payment that somehow gets settled event
                t1 = random_timestamp(base_time, 1)
                t2 = random_timestamp(t1, 2)
                t3 = random_timestamp(t2, 6)
                events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_INITIATED, amount, t1))
                event_count += 1
                events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_FAILED, amount, t2))
                event_count += 1
                events.append(_make_event(event_count, txn_id, merchant, EventType.SETTLED, amount, t3))
                event_count += 1
            else:
                # Premature settlement — initiated then settled (skipping processed)
                t1 = random_timestamp(base_time, 1)
                t2 = random_timestamp(t1, 6)
                events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_INITIATED, amount, t1))
                event_count += 1
                events.append(_make_event(event_count, txn_id, merchant, EventType.SETTLED, amount, t2))
                event_count += 1

        elif scenario == "stale_initiated":
            # Only initiated — stale (timestamp is old enough to be flagged)
            t1 = random_timestamp(BASE_DATE, 24)
            events.append(_make_event(event_count, txn_id, merchant, EventType.PAYMENT_INITIATED, amount, t1))
            event_count += 1

    # Shuffle to simulate out-of-order arrival
    random.shuffle(events)

    print(f"Generated {len(events)} events for {transaction_count} transactions")
    return events


def _make_event(idx: int, txn_id: str, merchant: dict, event_type: EventType, amount, timestamp) -> dict:
    """Create a single event dict."""
    return {
        "event_id": f"evt_{idx:06d}",
        "event_type": event_type.value,
        "transaction_id": txn_id,
        "merchant_id": merchant["id"],
        "merchant_name": merchant["name"],
        "amount": float(amount),
        "currency": "INR",
        "timestamp": timestamp.isoformat(),
    }


def seed_via_api(events: list[dict], base_url: str = "http://localhost:8000"):
    """Seed data by calling the POST /events API."""
    import httpx

    print(f"\nSeeding {len(events)} events via API at {base_url}...")
    duplicates = 0
    accepted = 0
    errors = 0

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for i, event in enumerate(events):
            # Remove internal flags
            payload = {k: v for k, v in event.items() if not k.startswith("_")}
            try:
                resp = client.post("/api/v1/events", json=payload)
                if resp.status_code == 201:
                    accepted += 1
                elif resp.status_code == 200:
                    duplicates += 1
                else:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error [{resp.status_code}]: {resp.text[:200]}")
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Request error: {e}")

            if (i + 1) % 1000 == 0:
                print(f"  Progress: {i+1}/{len(events)} (accepted={accepted}, duplicates={duplicates}, errors={errors})")

    print(f"\nSeed complete:")
    print(f"  Accepted:   {accepted}")
    print(f"  Duplicates: {duplicates}")
    print(f"  Errors:     {errors}")
    print(f"  Total:      {len(events)}")


def export_to_json(events: list[dict], filepath: str = "scripts/sample_events.json"):
    """Export generated events to JSON file."""
    # Remove internal flags
    clean_events = [{k: v for k, v in e.items() if not k.startswith("_")} for e in events]
    with open(filepath, "w") as f:
        json.dump(clean_events, f, indent=2, default=str)
    print(f"Exported {len(clean_events)} events to {filepath}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed payment events data")
    parser.add_argument(
        "--mode",
        choices=["api", "json", "both"],
        default="api",
        help="Seed mode: 'api' sends to running server, 'json' exports file, 'both' does both",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the running API server (for api mode)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Payment Event Seed Data Generator")
    print("=" * 60)

    events = generate_events()

    if args.mode in ("json", "both"):
        export_to_json(events)

    if args.mode in ("api", "both"):
        seed_via_api(events, base_url=args.url)
