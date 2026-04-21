"""
Tests for GET /transactions and GET /transactions/{transaction_id}.
"""


class TestTransactionList:

    def _seed_transactions(self, client):
        events = [
            {"event_id": "list_e1", "event_type": "payment_initiated", "transaction_id": "list_txn_1", "merchant_id": "list_m_A", "merchant_name": "Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-04-15T10:00:00Z"},
            {"event_id": "list_e2", "event_type": "payment_processed", "transaction_id": "list_txn_1", "merchant_id": "list_m_A", "merchant_name": "Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-04-15T11:00:00Z"},
            {"event_id": "list_e3", "event_type": "settled", "transaction_id": "list_txn_1", "merchant_id": "list_m_A", "merchant_name": "Merchant A", "amount": 1000, "currency": "INR", "timestamp": "2026-04-15T12:00:00Z"},
            {"event_id": "list_e4", "event_type": "payment_initiated", "transaction_id": "list_txn_2", "merchant_id": "list_m_B", "merchant_name": "Merchant B", "amount": 500, "currency": "INR", "timestamp": "2026-04-16T10:00:00Z"},
            {"event_id": "list_e5", "event_type": "payment_failed", "transaction_id": "list_txn_2", "merchant_id": "list_m_B", "merchant_name": "Merchant B", "amount": 500, "currency": "INR", "timestamp": "2026-04-16T11:00:00Z"},
            {"event_id": "list_e6", "event_type": "payment_initiated", "transaction_id": "list_txn_3", "merchant_id": "list_m_A", "merchant_name": "Merchant A", "amount": 2000, "currency": "INR", "timestamp": "2026-04-17T10:00:00Z"},
            {"event_id": "list_e7", "event_type": "payment_processed", "transaction_id": "list_txn_3", "merchant_id": "list_m_A", "merchant_name": "Merchant A", "amount": 2000, "currency": "INR", "timestamp": "2026-04-17T11:00:00Z"},
        ]
        for e in events:
            client.post("/api/v1/events", json=e)

    def test_list_all_transactions(self, client):
        self._seed_transactions(client)
        resp = client.get("/api/v1/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 3

    def test_filter_by_merchant_id(self, client):
        self._seed_transactions(client)
        resp = client.get("/api/v1/transactions?merchant_id=list_m_A")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 2

    def test_filter_by_payment_status(self, client):
        self._seed_transactions(client)
        resp = client.get("/api/v1/transactions?payment_status=failed")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 1

    def test_filter_by_date_range(self, client):
        self._seed_transactions(client)
        resp = client.get("/api/v1/transactions?date_from=2026-04-16T00:00:00Z&date_to=2026-04-17T23:59:59Z")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 2

    def test_pagination(self, client):
        self._seed_transactions(client)
        resp = client.get("/api/v1/transactions?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total_pages"] == 2

    def test_sorting_asc(self, client):
        self._seed_transactions(client)
        resp = client.get("/api/v1/transactions?sort_by=created_at&sort_order=asc")
        assert resp.status_code == 200
        dates = [i["created_at"] for i in resp.json()["items"]]
        assert dates == sorted(dates)


class TestTransactionDetail:

    def test_get_transaction_detail(self, client, sample_event, sample_processed_event):
        client.post("/api/v1/events", json=sample_event)
        client.post("/api/v1/events", json=sample_processed_event)
        resp = client.get(f"/api/v1/transactions/{sample_event['transaction_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_count"] == 2
        assert data["events"][0]["event_type"] == "payment_initiated"

    def test_transaction_not_found(self, client):
        resp = client.get("/api/v1/transactions/nonexistent")
        assert resp.status_code == 404

    def test_detail_includes_merchant_name(self, client, sample_event):
        client.post("/api/v1/events", json=sample_event)
        resp = client.get(f"/api/v1/transactions/{sample_event['transaction_id']}")
        assert resp.json()["merchant_name"] == sample_event["merchant_name"]
