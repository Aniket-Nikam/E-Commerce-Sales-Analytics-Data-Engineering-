from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import CHARTS_DIR, DB_PATH, PARQUET_DIR, PLANS_DIR, RAW_CSV, TABLES_DIR, ensure_directories


def _q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _timed(con: duckdb.DuckDBPyConnection, query: str, runs: int) -> tuple[float, list[float]]:
    con.execute(query).fetchall()
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        con.execute(query).fetchall()
        timings.append((time.perf_counter() - start) * 1000)
    return statistics.median(timings), timings


def run_benchmark(runs: int = 5, csv_path: Path = RAW_CSV, db_path: Path = DB_PATH) -> list[dict]:
    ensure_directories()
    parquet_glob = _q(PARQUET_DIR / "**" / "*.parquet")
    csv = _q(csv_path)
    results = []

    queries = {
        "CSV": f"""
            SELECT upper(trim(region)) AS region,
                   upper(substr(trim(category), 1, 1)) || lower(substr(trim(category), 2)) AS category,
                   SUM(TRY_CAST(quantity AS INTEGER) * TRY_CAST(unit_price AS DOUBLE) *
                       (1 - TRY_CAST(discount_pct AS DOUBLE) / 100.0)) AS revenue
            FROM read_csv('{csv}', header=true, all_varchar=true, ignore_errors=true)
            WHERE lower(trim(order_status)) IN ('delivered','shipped')
              AND TRY_CAST(quantity AS INTEGER) BETWEEN 1 AND 20
              AND TRY_CAST(unit_price AS DOUBLE) > 0
              AND TRY_CAST(discount_pct AS DOUBLE) BETWEEN 0 AND 80
            GROUP BY 1, 2 ORDER BY 3 DESC
        """,
        "Parquet": f"""
            SELECT region, category, SUM(net_revenue) AS revenue
            FROM read_parquet('{parquet_glob}', hive_partitioning=true)
            WHERE order_status IN ('Delivered','Shipped')
            GROUP BY 1, 2 ORDER BY 3 DESC
        """,
        "DuckDB": """
            SELECT region, category, SUM(net_revenue) AS revenue
            FROM warehouse.vw_sales_enriched
            WHERE order_status IN ('Delivered','Shipped')
            GROUP BY 1, 2 ORDER BY 3 DESC
        """,
    }

    for threads in (1, 4):
        con = duckdb.connect(str(db_path), read_only=True)
        con.execute(f"SET threads = {threads}")
        for storage, query in queries.items():
            median_ms, timings = _timed(con, query, runs)
            results.append({
                "storage": storage,
                "threads": threads,
                "median_ms": round(median_ms, 3),
                "min_ms": round(min(timings), 3),
                "max_ms": round(max(timings), 3),
                "runs": runs,
            })
        if threads == 4:
            plan = con.execute("EXPLAIN ANALYZE " + queries["DuckDB"]).fetchone()[1]
            (PLANS_DIR / "benchmark_duckdb_4_threads.txt").write_text(plan, encoding="utf-8")
        con.close()

    frame = pd.DataFrame(results)
    frame.to_csv(TABLES_DIR / "benchmark_results.csv", index=False)
    (TABLES_DIR / "benchmark_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    pivot = frame.pivot(index="storage", columns="threads", values="median_ms").reindex(["CSV", "Parquet", "DuckDB"])
    ax = pivot.plot(kind="bar", figsize=(9.5, 5.3), color=["#5267D7", "#16B8A6"], width=0.72)
    ax.set_title("Median query time by storage and thread mode", fontsize=15, fontweight="bold", loc="left")
    ax.set_ylabel("Median time (ms), lower is better")
    ax.set_xlabel("")
    ax.grid(axis="y", alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(title="Threads", frameon=False)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "benchmark_results.png", dpi=180, bbox_inches="tight")
    plt.close()
    return results
