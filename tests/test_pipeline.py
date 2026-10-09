from pathlib import Path

import duckdb

from src.analytics import run_analytics
from src.generate_data import generate_dataset
from src.pipeline import build_warehouse


def test_end_to_end_smoke(tmp_path: Path):
    csv_path = tmp_path / "orders.csv"
    db_path = tmp_path / "test.duckdb"
    generated = generate_dataset(5_000, 7, csv_path)
    quality = build_warehouse(csv_path, db_path, tmp_path / "parquet")
    assert generated["written_rows"] > 5_000
    assert quality["clean_rows"] > 4_900
    con = duckdb.connect(str(db_path), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM warehouse.dim_product").fetchone()[0] == 48
    assert con.execute("SELECT repeat_customer_pct FROM warehouse.vw_repeat_customer_pct").fetchone()[0] > 0
    con.close()
