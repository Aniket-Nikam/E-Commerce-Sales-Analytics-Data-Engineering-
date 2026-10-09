from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import duckdb

from .config import DB_PATH, PARQUET_DIR, RAW_CSV, RESULTS_DIR, ensure_directories


def sql_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "sql" / name


def _quote(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def build_warehouse(
    input_csv: Path = RAW_CSV,
    db_path: Path = DB_PATH,
    parquet_dir: Path = PARQUET_DIR,
) -> dict:
    ensure_directories()
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")
    if db_path.exists():
        db_path.unlink()
    if parquet_dir.exists():
        shutil.rmtree(parquet_dir)

    started = time.perf_counter()
    con = duckdb.connect(str(db_path))
    con.execute("SET threads = 4")
    con.execute("SET preserve_insertion_order = false")
    con.execute("CREATE SCHEMA IF NOT EXISTS warehouse")

    raw = _quote(input_csv)
    con.execute(f"""
        CREATE OR REPLACE TABLE warehouse.raw_orders AS
        SELECT *
        FROM read_csv('{raw}', header = true, all_varchar = true,
                      auto_detect = true, ignore_errors = true)
    """)

    con.execute(sql_path("schema.sql").read_text(encoding="utf-8"))
    con.execute(sql_path("views.sql").read_text(encoding="utf-8"))

    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet = _quote(parquet_dir)
    con.execute(f"""
        COPY (
            SELECT
                order_date, order_id, line_id, customer_id, customer_segment,
                region, sales_channel, product_id, product_name, category,
                quantity, unit_price, discount_pct, gross_amount, net_revenue,
                payment_method, order_status, shipping_days,
                EXTRACT(year FROM order_date)::INTEGER AS year,
                EXTRACT(month FROM order_date)::INTEGER AS month
            FROM warehouse.vw_sales_enriched
        ) TO '{parquet}' (
            FORMAT PARQUET,
            PARTITION_BY (year, month),
            COMPRESSION ZSTD,
            OVERWRITE_OR_IGNORE true
        )
    """)

    quality = con.execute("""
        SELECT
            (SELECT COUNT(*) FROM warehouse.raw_orders) AS raw_rows,
            (SELECT COUNT(*) FROM warehouse.stg_orders) AS typed_rows,
            (SELECT COUNT(*) FROM warehouse.fact_sales) AS clean_rows,
            (SELECT COUNT(*) FROM warehouse.rejected_orders) AS rejected_rows,
            (SELECT COUNT(DISTINCT order_id) FROM warehouse.fact_sales) AS orders,
            (SELECT COUNT(*) FROM warehouse.dim_customer) AS customers,
            (SELECT COUNT(*) FROM warehouse.dim_product) AS products,
            (SELECT MIN(order_date) FROM warehouse.fact_sales) AS min_date,
            (SELECT MAX(order_date) FROM warehouse.fact_sales) AS max_date
    """).fetchdf().iloc[0].to_dict()
    quality = {key: (value.isoformat() if hasattr(value, "isoformat") else int(value) if hasattr(value, "item") else value) for key, value in quality.items()}
    quality["duration_seconds"] = round(time.perf_counter() - started, 3)
    quality["database_mb"] = round(db_path.stat().st_size / (1024 * 1024), 3)
    quality["parquet_mb"] = round(sum(p.stat().st_size for p in parquet_dir.rglob("*.parquet")) / (1024 * 1024), 3)

    if db_path.resolve() == DB_PATH.resolve():
        (RESULTS_DIR / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    con.close()
    return quality


def load_api_snapshot(csv_path: Path, db_path: Path = DB_PATH) -> int:
    if not db_path.exists():
        return 0
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS warehouse")
    con.execute(f"""
        CREATE OR REPLACE TABLE warehouse.api_cart_items AS
        SELECT * FROM read_csv_auto('{_quote(csv_path)}', header = true)
    """)
    count = con.execute("SELECT COUNT(*) FROM warehouse.api_cart_items").fetchone()[0]
    con.close()
    return int(count)
