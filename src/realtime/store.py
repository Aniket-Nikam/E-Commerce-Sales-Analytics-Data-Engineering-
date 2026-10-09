from __future__ import annotations

import threading
from pathlib import Path

import duckdb

from .models import OrderEvent


DDL = """
CREATE SCHEMA IF NOT EXISTS streaming;

CREATE TABLE IF NOT EXISTS streaming.order_events (
    event_id VARCHAR PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL,
    order_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(12, 2) NOT NULL CHECK (unit_price > 0),
    discount_pct DECIMAL(5, 4) NOT NULL CHECK (discount_pct BETWEEN 0 AND 0.8),
    region VARCHAR NOT NULL,
    sales_channel VARCHAR NOT NULL,
    net_revenue DECIMAL(14, 2) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);

CREATE OR REPLACE VIEW streaming.vw_events_by_minute AS
SELECT
    date_trunc('minute', event_time) AS event_minute,
    COUNT(*) AS event_count,
    SUM(net_revenue) AS revenue
FROM streaming.order_events
GROUP BY event_minute;
"""


class RealtimeStore:
    """Single-process owner for the real-time DuckDB staging database."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def initialize(self) -> None:
        with self._lock, self._connect() as con:
            con.execute(DDL)

    def insert(self, event: OrderEvent) -> bool:
        with self._lock, self._connect() as con:
            row = con.execute(
                """
                INSERT INTO streaming.order_events (
                    event_id, event_time, order_id, customer_id, product_id,
                    category, quantity, unit_price, discount_pct, region,
                    sales_channel, net_revenue
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """,
                [
                    str(event.event_id),
                    event.event_time,
                    event.order_id,
                    event.customer_id,
                    event.product_id,
                    event.category,
                    event.quantity,
                    event.unit_price,
                    event.discount_pct,
                    event.region,
                    event.sales_channel,
                    event.net_revenue,
                ],
            ).fetchone()
        return row is not None

    def metrics(self) -> dict:
        with self._lock, self._connect() as con:
            row = con.execute(
                """
                SELECT
                    COUNT(*) AS total_events,
                    COALESCE(SUM(net_revenue), 0) AS live_revenue,
                    COUNT(*) FILTER (
                        WHERE event_time >= current_timestamp - INTERVAL '60 seconds'
                    ) AS events_last_60_seconds,
                    MAX(event_time) AS last_event_time,
                    COUNT(DISTINCT customer_id) AS live_customers
                FROM streaming.order_events
                """
            ).fetchone()
        return {
            "total_events": int(row[0]),
            "live_revenue": float(row[1]),
            "events_last_60_seconds": int(row[2]),
            "last_event_time": row[3].isoformat() if row[3] else None,
            "live_customers": int(row[4]),
        }

    def recent(self, limit: int = 20) -> list[dict]:
        safe_limit = min(max(int(limit), 1), 100)
        with self._lock, self._connect() as con:
            rows = con.execute(
                """
                SELECT event_id, event_time, order_id, customer_id, product_id,
                       category, quantity, unit_price, discount_pct, region,
                       sales_channel, net_revenue, received_at
                FROM streaming.order_events
                ORDER BY received_at DESC
                LIMIT ?
                """,
                [safe_limit],
            ).fetchdf()
        if rows.empty:
            return []
        for column in ("event_time", "received_at"):
            rows[column] = rows[column].astype(str)
        return rows.to_dict(orient="records")
