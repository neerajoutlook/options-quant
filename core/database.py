import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TradingDatabase:
    def __init__(self, db_path: str = "data/trading_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            # Orders Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    qty INTEGER,
                    price REAL,
                    status TEXT,
                    timestamp TEXT,
                    raw_data TEXT
                )
            """)
            
            # Positions Table (Keyed by Symbol + Product Type)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT,
                    product TEXT,
                    net_qty INTEGER,
                    avg_price REAL,
                    realized_pnl REAL,
                    last_updated TEXT,
                    PRIMARY KEY (symbol, product)
                )
            """)
            
            # Migration: Ensure 'product' column exists (if someone had an old DB)
            try:
                conn.execute("ALTER TABLE positions ADD COLUMN product TEXT DEFAULT 'I'")
            except:
                pass # Already exists
            
            # App State (e.g. Total Realized P&L)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def save_order(self, order: Dict[str, Any]):
        """Save or update an order"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO orders (id, symbol, side, qty, price, status, timestamp, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.get('id'),
                    order.get('symbol'),
                    order.get('side'),
                    order.get('qty'),
                    order.get('price'),
                    order.get('status'),
                    order.get('timestamp', datetime.now().isoformat()),
                    json.dumps(order)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving order to DB: {e}")

    def get_recent_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent orders from DB"""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT raw_data FROM orders ORDER BY timestamp DESC LIMIT ?", (limit,))
                return [json.loads(row['raw_data']) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching orders from DB: {e}")
            return []

    def get_orders_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """Fetch orders for a specific date (YYYY-MM-DD)"""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                # Use LIKE or substr to match the date part of ISO timestamp
                cursor = conn.execute("SELECT raw_data FROM orders WHERE timestamp LIKE ? ORDER BY timestamp DESC", (f"{date_str}%",))
                return [json.loads(row['raw_data']) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error filtering orders by date: {e}")
            return []

    def clear_orders_for_date(self, date_str: str):
        """Clear all orders for a specific date"""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM orders WHERE timestamp LIKE ?", (f"{date_str}%",))
                conn.commit()
                logger.info(f"🗑️ Database: Cleared orders for date {date_str}")
        except Exception as e:
            logger.error(f"Error clearing orders for date {date_str}: {e}")

    def save_position(self, symbol: str, pos_data: Dict[str, Any], product: str = 'I'):
        """Save position state for a symbol + product"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO positions (symbol, product, net_qty, avg_price, realized_pnl, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    product,
                    pos_data.get('net_qty', 0),
                    pos_data.get('avg_price', 0.0),
                    pos_data.get('realized_pnl', 0.0),
                    datetime.now().isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving position to DB: {e}")

    def get_positions(self) -> Dict[str, Any]:
        """Load all saved positions as {(symbol, product): data}"""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM positions")
                return {(row['symbol'], row['product'] or 'I'): {
                    'net_qty': row['net_qty'],
                    'avg_price': row['avg_price'],
                    'realized_pnl': row['realized_pnl'],
                    'unrealized_pnl': 0.0 # Calculated at runtime
                } for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error loading positions from DB: {e}")
            return {}

    def save_state(self, key: str, value: Any):
        """Save simple key-value state"""
        try:
            with self._get_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)", (key, str(value)))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving state to DB: {e}")

    def get_state(self, key: str, default: Any = None) -> Any:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else default
        except Exception as e:
            logger.error(f"Error getting state from DB: {e}")
            return default

# Global instance
db = TradingDatabase()
