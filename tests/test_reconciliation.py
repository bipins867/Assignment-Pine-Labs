"""
Tests for GET /reconciliation/summary and GET /reconciliation/discrepancies.
"""


class TestReconciliationSummary:

    def _seed_data(self, client):
        """Create mixed transactions for reconciliation testing."""
        events = [
            # Txn 1: full lifecycle (merchant A)
            {"event_id": "rec_e1", "event_type": "payment_initiated", "transaction_id": "rec_txn_1", "merchant_id": "rec_m_A", "merchant_name": "Rec Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-04-10T10:00:00Z"},
            {"event_id": "rec_e2", "event_type": "payment_processed", "transaction_id": "rec_txn_1", "merchant_id": "rec_m_A", "merchant_name": "Rec Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-04-10T11:00:00Z"},
            {"event_id": "rec_e3", "event_type": "settled", "transaction_id": "rec_txn_1", "merchant_id": "rec_m_A", "merchant_name": "Rec Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-04-10T12:00:00Z"},
            # Txn 2: processed but unsettled (merchant A) — discrepancy
            {"event_id": "rec_e4", "event_type": "payment_initiated", "transaction_id": "rec_txn_2", "merchant_id": "rec_m_A", "merchant_name": "Rec Merchant A", "amount": 2000, "currency": "INR", "timestamp": "2026-04-10T10:00:00Z"},
            {"event_id": "rec_e5", "event_type": "payment_processed", "transaction_id": "rec_txn_2", "merchant_id": "rec_m_A", "merchant_name": "Rec Merchant A", "amount": 2000, "currency": "INR", "timestamp": "2026-04-10T11:00:00Z"},
            # Txn 3: failed (merchant B)
            {"event_id": "rec_e6", "event_type": "payment_initiated", "transaction_id": "rec_txn_3", "merchant_id": "rec_m_B", "merchant_name": "Rec Merchant B", "amount": 500, "currency": "INR", "timestamp": "2026-04-11T10:00:00Z"},
            {"event_id": "rec_e7", "event_type": "payment_failed", "transaction_id": "rec_txn_3", "merchant_id": "rec_m_B", "merchant_name": "Rec Merchant B", "amount": 500, "currency": "INR", "timestamp": "2026-04-11T11:00:00Z"},
            # Txn 4: stale initiated (merchant B) — discrepancy
            {"event_id": "rec_e8", "event_type": "payment_initiated", "transaction_id": "rec_txn_4", "merchant_id": "rec_m_B", "merchant_name": "Rec Merchant B", "amount": 750, "currency": "INR", "timestamp": "2026-04-01T10:00:00Z"},
        ]
        for e in events:
            client.post("/api/v1/events", json=e)

    def test_summary_by_merchant(self, client):
        self._seed_data(client)
        resp = client.get("/api/v1/reconciliation/summary?group_by=merchant")
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_by"] == "merchant"
        assert len(data["groups"]) == 2  # rec_m_A and rec_m_B
        assert data["totals"]["total_transactions"] == 4

    def test_summary_by_date(self, client):
        self._seed_data(client)
        resp = client.get("/api/v1/reconciliation/summary?group_by=date")
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_by"] == "date"
        assert len(data["groups"]) >= 2

    def test_summary_by_status(self, client):
        self._seed_data(client)
        resp = client.get("/api/v1/reconciliation/summary?group_by=status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_by"] == "status"

    def test_summary_filter_by_merchant(self, client):
        self._seed_data(client)
        resp = client.get("/api/v1/reconciliation/summary?group_by=merchant&merchant_id=rec_m_A")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totals"]["total_transactions"] == 2

    def test_summary_totals_include_settlement_rate(self, client):
        self._seed_data(client)
        resp = client.get("/api/v1/reconciliation/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "settlement_rate" in data["totals"]


class TestReconciliationDiscrepancies:

    def _seed_discrepancies(self, client):
        """Create transactions with known discrepancies."""
        events = [
            # Txn 1: processed but unsettled (old timestamp = stale)
            {"event_id": "disc_e1", "event_type": "payment_initiated", "transaction_id": "disc_txn_1", "merchant_id": "disc_m_A", "merchant_name": "Disc Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-03-01T10:00:00Z"},
            {"event_id": "disc_e2", "event_type": "payment_processed", "transaction_id": "disc_txn_1", "merchant_id": "disc_m_A", "merchant_name": "Disc Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-03-01T11:00:00Z"},
            # Txn 2: stale initiated
            {"event_id": "disc_e3", "event_type": "payment_initiated", "transaction_id": "disc_txn_2", "merchant_id": "disc_m_A", "merchant_name": "Disc Merchant A", "amount": 500, "currency": "INR", "timestamp": "2026-03-01T10:00:00Z"},
            # Txn 3: normal settled (should NOT be a discrepancy)
            {"event_id": "disc_e4", "event_type": "payment_initiated", "transaction_id": "disc_txn_3", "merchant_id": "disc_m_A", "merchant_name": "Disc Merchant A", "amount": 2000, "currency": "INR", "timestamp": "2026-04-20T10:00:00Z"},
            {"event_id": "disc_e5", "event_type": "payment_processed", "transaction_id": "disc_txn_3", "merchant_id": "disc_m_A", "merchant_name": "Disc Merchant A", "amount": 2000, "currency": "INR", "timestamp": "2026-04-20T11:00:00Z"},
            {"event_id": "disc_e6", "event_type": "settled", "transaction_id": "disc_txn_3", "merchant_id": "disc_m_A", "merchant_name": "Disc Merchant A", "amount": 2000, "currency": "INR", "timestamp": "2026-04-20T12:00:00Z"},
        ]
        for e in events:
            client.post("/api/v1/events", json=e)

    def test_discrepancies_detected(self, client):
        self._seed_discrepancies(client)
        resp = client.get("/api/v1/reconciliation/discrepancies?stale_after_hours=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        types = [i["discrepancy_type"] for i in data["items"]]
        assert "unsettled_processed" in types
        assert "stale_initiated" in types

    def test_discrepancies_filter_by_type(self, client):
        self._seed_discrepancies(client)
        resp = client.get("/api/v1/reconciliation/discrepancies?discrepancy_type=unsettled_processed&stale_after_hours=1")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["discrepancy_type"] == "unsettled_processed"

    def test_discrepancies_configurable_threshold(self, client):
        self._seed_discrepancies(client)
        resp = client.get("/api/v1/reconciliation/discrepancies?stale_after_hours=1")
        assert resp.status_code == 200
        assert resp.json()["stale_after_hours"] == 1.0

    def test_discrepancy_summary_counts(self, client):
        self._seed_discrepancies(client)
        resp = client.get("/api/v1/reconciliation/discrepancies?stale_after_hours=1")
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        assert "unsettled_processed" in summary
        assert "stale_initiated" in summary
        assert summary["total"] == resp.json()["total"]

    def test_discrepancies_invalid_threshold_returns_422(self, client):
        resp = client.get("/api/v1/reconciliation/discrepancies?stale_after_hours=-5")
        assert resp.status_code == 422
