"""
Test fixtures — MySQL test database with transactional isolation.

Each test runs inside a transaction that is rolled back on completion,
ensuring test isolation without needing to truncate tables between tests.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.dependencies.database import get_db

# Import all models so Base.metadata knows about them
from app.models.merchant import Merchant  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.payment_event import PaymentEvent  # noqa: F401

settings = get_settings()

# Create test engine pointing at the test database
test_engine = create_engine(
    settings.TEST_DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Create all tables in the test database once per test session.
    Drop all tables after the session completes.
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Provide a transactional database session for each test.
    The transaction is rolled back after each test for isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI test client with the database session overridden
    to use the test database with transactional isolation.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Helper fixtures ---

@pytest.fixture
def sample_event():
    """Return a valid event payload for testing."""
    return {
        "event_id": "test_evt_001",
        "event_type": "payment_initiated",
        "transaction_id": "test_txn_001",
        "merchant_id": "test_merchant_A",
        "merchant_name": "Test Merchant A",
        "amount": 1500.00,
        "currency": "INR",
        "timestamp": "2026-04-20T10:30:00Z",
    }


@pytest.fixture
def sample_processed_event():
    """Return a payment_processed event payload."""
    return {
        "event_id": "test_evt_002",
        "event_type": "payment_processed",
        "transaction_id": "test_txn_001",
        "merchant_id": "test_merchant_A",
        "merchant_name": "Test Merchant A",
        "amount": 1500.00,
        "currency": "INR",
        "timestamp": "2026-04-20T11:00:00Z",
    }


@pytest.fixture
def sample_settled_event():
    """Return a settled event payload."""
    return {
        "event_id": "test_evt_003",
        "event_type": "settled",
        "transaction_id": "test_txn_001",
        "merchant_id": "test_merchant_A",
        "merchant_name": "Test Merchant A",
        "amount": 1500.00,
        "currency": "INR",
        "timestamp": "2026-04-20T12:00:00Z",
    }


@pytest.fixture
def sample_failed_event():
    """Return a payment_failed event payload."""
    return {
        "event_id": "test_evt_fail_001",
        "event_type": "payment_failed",
        "transaction_id": "test_txn_002",
        "merchant_id": "test_merchant_A",
        "merchant_name": "Test Merchant A",
        "amount": 750.00,
        "currency": "INR",
        "timestamp": "2026-04-20T10:45:00Z",
    }
