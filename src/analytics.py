from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import CHARTS_DIR, DB_PATH, PLANS_DIR, TABLES_DIR, ensure_directories

COLORS = ["#16B8A6", "#F2A03D", "#5267D7", "#E65B65", "#7E57C2", "#3B8C5A"]


def _save_table(con: duckdb.DuckDBPyConnection, name: str, query: str) -> pd.DataFrame:
    df = con.execute(query).fetchdf()
    df.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    return df


def _style_axis(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)


def run_analytics(db_path: Path = DB_PATH) -> dict:
    ensure_directories()
    if not db_path.exists():
        raise FileNotFoundError(f"Warehouse not found: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)

    monthly = _save_table(con, "monthly_growth", "SELECT * FROM warehouse.vw_monthly_growth ORDER BY sales_month")
    category = _save_table(con, "category_performance", """
        SELECT category,
               ROUND(SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END), 2) AS revenue,
               COUNT(DISTINCT order_id) AS orders,
               ROUND(100.0 * COUNT_IF(order_status = 'Returned') / COUNT(*), 2) AS return_rate_pct
        FROM warehouse.vw_sales_enriched GROUP BY category ORDER BY revenue DESC
    """)
    region = _save_table(con, "region_performance", """
        SELECT region,
               ROUND(SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END), 2) AS revenue,
               COUNT(DISTINCT order_id) AS orders
        FROM warehouse.vw_sales_enriched GROUP BY region ORDER BY revenue DESC
    """)
    customers = _save_table(con, "top_customers", """
        SELECT customer_id, customer_segment, region,
               ROUND(SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END), 2) AS revenue,
               COUNT(DISTINCT order_id) AS orders,
               DENSE_RANK() OVER (ORDER BY SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END) DESC) AS revenue_rank
        FROM warehouse.vw_sales_enriched
        GROUP BY customer_id, customer_segment, region
        ORDER BY revenue_rank LIMIT 20
    """)
    repeat = _save_table(con, "repeat_customer_pct", "SELECT * FROM warehouse.vw_repeat_customer_pct")
    grouping_sets = _save_table(con, "grouping_sets", """
        SELECT COALESCE(region, 'ALL REGIONS') AS region,
               COALESCE(category, 'ALL CATEGORIES') AS category,
               ROUND(SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END), 2) AS revenue,
               GROUPING(region) AS region_total,
               GROUPING(category) AS category_total
        FROM warehouse.vw_sales_enriched
        GROUP BY GROUPING SETS ((region, category), (region), (category), ())
        ORDER BY region_total, category_total, revenue DESC
    """)

    plt.figure(figsize=(10, 5.2))
    ax = plt.gca()
    ax.plot(pd.to_datetime(monthly["sales_month"]), monthly["revenue"], color=COLORS[0], linewidth=2.6)
    ax.fill_between(pd.to_datetime(monthly["sales_month"]), monthly["revenue"], color=COLORS[0], alpha=0.12)
    _style_axis(ax, "Monthly realized revenue", ylabel="Revenue (USD)")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "monthly_revenue.png", dpi=180, bbox_inches="tight")
    plt.close()

    cat_plot = category.sort_values("revenue")
    plt.figure(figsize=(9, 5.2))
    ax = plt.gca()
    ax.barh(cat_plot["category"], cat_plot["revenue"], color=COLORS[: len(cat_plot)])
    _style_axis(ax, "Revenue by product category", xlabel="Revenue (USD)")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "category_revenue.png", dpi=180, bbox_inches="tight")
    plt.close()

    reg_plot = region.sort_values("revenue")
    plt.figure(figsize=(9, 5.2))
    ax = plt.gca()
    ax.barh(reg_plot["region"], reg_plot["revenue"], color=COLORS[2])
    _style_axis(ax, "Revenue by region", xlabel="Revenue (USD)")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "region_revenue.png", dpi=180, bbox_inches="tight")
    plt.close()

    ret_plot = category.sort_values("return_rate_pct")
    plt.figure(figsize=(9, 5.2))
    ax = plt.gca()
    ax.barh(ret_plot["category"], ret_plot["return_rate_pct"], color=COLORS[3])
    _style_axis(ax, "Return rate by category", xlabel="Return rate (%)")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "return_rate.png", dpi=180, bbox_inches="tight")
    plt.close()

    kpis = con.execute("""
        SELECT
            ROUND(SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END), 2) AS revenue,
            COUNT(DISTINCT order_id) AS orders,
            COUNT(DISTINCT customer_id) AS customers,
            ROUND(AVG(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue END), 2) AS avg_line_value,
            ROUND(100.0 * COUNT_IF(order_status = 'Returned') / COUNT(*), 2) AS return_rate_pct
        FROM warehouse.vw_sales_enriched
    """).fetchdf().iloc[0].to_dict()
    kpis = {k: float(v) if hasattr(v, "item") else v for k, v in kpis.items()}
    kpis["repeat_customer_pct"] = float(repeat.iloc[0]["repeat_customer_pct"])
    kpis["top_category"] = str(category.iloc[0]["category"])
    kpis["top_region"] = str(region.iloc[0]["region"])
    kpis["top_customer"] = str(customers.iloc[0]["customer_id"])
    kpis["grouping_set_rows"] = int(len(grouping_sets))
    (TABLES_DIR / "kpis.json").write_text(json.dumps(kpis, indent=2), encoding="utf-8")

    plan = con.execute("EXPLAIN ANALYZE SELECT category, SUM(net_revenue) FROM warehouse.vw_sales_enriched WHERE order_status IN ('Delivered','Shipped') GROUP BY category").fetchone()[1]
    (PLANS_DIR / "category_revenue_explain_analyze.txt").write_text(plan, encoding="utf-8")
    con.close()
    return kpis

