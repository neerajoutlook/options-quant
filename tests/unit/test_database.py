import pytest
import os
from core.database import TradingDatabase

@pytest.fixture
def test_db():
    # Use a temporary file for testing
    db_file = "data/test_trading.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    db = TradingDatabase(db_path=db_file)
    yield db
    # Cleanup after tests
    if os.path.exists(db_file):
        os.remove(db_file)

def test_db_save_and_fetch_orders(test_db):
    order = {
        "id": "ORD123",
        "symbol": "BANKNIFTY",
        "side": "BUY",
        "qty": 15,
        "price": 50000.0,
        "status": "COMPLETE",
        "timestamp": "2026-01-05T10:00:00"
    }
    test_db.save_order(order)
    
    orders = test_db.get_recent_orders()
    assert len(orders) == 1
    assert orders[0]["id"] == "ORD123"

def test_db_filter_by_date(test_db):
    test_db.save_order({"id": "O1", "timestamp": "2026-01-01T12:00:00"})
    test_db.save_order({"id": "O2", "timestamp": "2026-01-02T12:00:00"})
    
    jan1_orders = test_db.get_orders_by_date("2026-01-01")
    assert len(jan1_orders) == 1
    assert jan1_orders[0]["id"] == "O1"

def test_db_clear_by_date(test_db):
    test_db.save_order({"id": "O1", "timestamp": "2026-01-01T12:00:00"})
    test_db.save_order({"id": "O2", "timestamp": "2026-01-02T12:00:00"})
    
    test_db.clear_orders_for_date("2026-01-01")
    
    remaining = test_db.get_recent_orders()
    assert len(remaining) == 1
    assert remaining[0]["id"] == "O2"

def test_db_app_state(test_db):
    test_db.save_state("test_key", "test_value")
    val = test_db.get_state("test_key")
    assert val == "test_value"
