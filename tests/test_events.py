"""
Tests for POST /events — event ingestion, idempotency, state transitions.
"""

import pytest


class TestEventIngestion:
    """Test suite for the event ingestion endpoint."""

    def test_ingest_valid_event_returns_201(self, client, sample_event):
        """A valid new event should be accepted with 201."""
        resp = client.post("/api/v1/events", json=sample_event)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["is_duplicate"] is False
        assert data["event_id"] == sample_event["event_id"]
        assert data["transaction_id"] == sample_event["transaction_id"]
        assert data["payment_status"] == "initiated"
        assert data["settlement_status"] == "pending"

    def test_duplicate_event_returns_200(self, client, sample_event):
        """Submitting the same event_id twice should return 200 with is_duplicate=True."""
        # First submission
        resp1 = client.post("/api/v1/events", json=sample_event)
        assert resp1.status_code == 201

        # Duplicate submission
        resp2 = client.post("/api/v1/events", json=sample_event)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "duplicate"
        assert data["is_duplicate"] is True

    def test_idempotency_preserves_state(self, client, sample_event, sample_processed_event):
        """Duplicate event should not change transaction state."""
        # Create transaction
        client.post("/api/v1/events", json=sample_event)

        # Process it
        client.post("/api/v1/events", json=sample_processed_event)

        # Replay the initiated event — should not revert state
        resp = client.post("/api/v1/events", json=sample_event)
        assert resp.status_code == 200
        assert resp.json()["payment_status"] == "processed"

    def test_full_lifecycle_transition(self, client, sample_event, sample_processed_event, sample_settled_event):
        """initiated → processed → settled lifecycle should work correctly."""
        resp1 = client.post("/api/v1/events", json=sample_event)
        assert resp1.status_code == 201
        assert resp1.json()["payment_status"] == "initiated"

        resp2 = client.post("/api/v1/events", json=sample_processed_event)
        assert resp2.status_code == 201
        assert resp2.json()["payment_status"] == "processed"
        assert resp2.json()["settlement_status"] == "pending"

        resp3 = client.post("/api/v1/events", json=sample_settled_event)
        assert resp3.status_code == 201
        assert resp3.json()["payment_status"] == "processed"
        assert resp3.json()["settlement_status"] == "settled"

    def test_failed_transition(self, client):
        """initiated → failed should set correct statuses."""
        # Create initiated
        init_event = {
            "event_id": "fail_init_001",
            "event_type": "payment_initiated",
            "transaction_id": "fail_txn_001",
            "merchant_id": "test_merchant_B",
            "merchant_name": "Test Merchant B",
            "amount": 500.00,
            "currency": "INR",
            "timestamp": "2026-04-20T10:00:00Z",
        }
        client.post("/api/v1/events", json=init_event)

        # Fail it
        fail_event = {
            "event_id": "fail_evt_001",
            "event_type": "payment_failed",
            "transaction_id": "fail_txn_001",
            "merchant_id": "test_merchant_B",
            "merchant_name": "Test Merchant B",
            "amount": 500.00,
            "currency": "INR",
            "timestamp": "2026-04-20T10:05:00Z",
        }
        resp = client.post("/api/v1/events", json=fail_event)
        assert resp.status_code == 201
        assert resp.json()["payment_status"] == "failed"
        assert resp.json()["settlement_status"] == "not_applicable"

    def test_terminal_state_blocks_transition(self, client):
        """Events after terminal state should be recorded but not change state."""
        # Create full lifecycle
        events = [
            {"event_id": "term_e1", "event_type": "payment_initiated", "transaction_id": "term_txn", "merchant_id": "m1", "merchant_name": "M1", "amount": 100, "currency": "INR", "timestamp": "2026-04-20T10:00:00Z"},
            {"event_id": "term_e2", "event_type": "payment_processed", "transaction_id": "term_txn", "merchant_id": "m1", "merchant_name": "M1", "amount": 100, "currency": "INR", "timestamp": "2026-04-20T11:00:00Z"},
            {"event_id": "term_e3", "event_type": "settled", "transaction_id": "term_txn", "merchant_id": "m1", "merchant_name": "M1", "amount": 100, "currency": "INR", "timestamp": "2026-04-20T12:00:00Z"},
        ]
        for e in events:
            client.post("/api/v1/events", json=e)

        # Try to process again after settled (terminal)
        late_event = {
            "event_id": "term_e4",
            "event_type": "payment_failed",
            "transaction_id": "term_txn",
            "merchant_id": "m1",
            "merchant_name": "M1",
            "amount": 100,
            "currency": "INR",
            "timestamp": "2026-04-20T13:00:00Z",
        }
        resp = client.post("/api/v1/events", json=late_event)
        assert resp.status_code == 201
        # State should remain settled, not failed
        assert resp.json()["payment_status"] == "processed"
        assert resp.json()["settlement_status"] == "settled"
        assert resp.json()["message"] is not None  # Warning message

    def test_invalid_payload_returns_422(self, client):
        """Missing required fields should return 422."""
        resp = client.post("/api/v1/events", json={"event_id": "x"})
        assert resp.status_code == 422

    def test_invalid_event_type_returns_422(self, client, sample_event):
        """Invalid event_type should return 422."""
        payload = sample_event.copy()
        payload["event_type"] = "invalid_type"
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422

    def test_negative_amount_returns_422(self, client, sample_event):
        """Negative amount should be rejected."""
        payload = sample_event.copy()
        payload["amount"] = -100.00
        resp = client.post("/api/v1/events", json=payload)
        assert resp.status_code == 422
