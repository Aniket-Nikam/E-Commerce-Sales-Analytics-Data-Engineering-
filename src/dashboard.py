from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DB_PATH

st.set_page_config(
    page_title="E-Commerce Sales Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def connection() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        st.error("Warehouse not found. Run: python -m src.cli all --rows 250000")
        st.stop()
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(ttl=120)
def query(sql: str, params: list | None = None) -> pd.DataFrame:
    return connection().execute(sql, params or []).fetchdf()


st.title("E-Commerce Sales Analytics")
st.caption("DuckDB warehouse with partitioned Parquet and reproducible Python ETL")


def compact_money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"

filters = query("""
    SELECT MIN(order_date)::DATE AS min_date, MAX(order_date)::DATE AS max_date,
           list_sort(list_distinct(list(region))) AS regions,
           list_sort(list_distinct(list(category))) AS categories
    FROM warehouse.vw_sales_enriched
""").iloc[0]

with st.sidebar:
    st.header("Filters")
    date_range = st.date_input("Order date", value=(filters["min_date"], filters["max_date"]))
    selected_regions = st.multiselect("Region", filters["regions"], default=filters["regions"])
    selected_categories = st.multiselect("Category", filters["categories"], default=filters["categories"])

if len(date_range) != 2 or not selected_regions or not selected_categories:
    st.warning("Select a complete date range, at least one region, and at least one category.")
    st.stop()

region_marks = ",".join("?" for _ in selected_regions)
category_marks = ",".join("?" for _ in selected_categories)
where = f"order_date::DATE BETWEEN ? AND ? AND region IN ({region_marks}) AND category IN ({category_marks})"
params = [date_range[0], date_range[1], *selected_regions, *selected_categories]

kpis = query(f"""
    SELECT
        SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END) AS revenue,
        COUNT(DISTINCT order_id) AS orders,
        COUNT(DISTINCT customer_id) AS customers,
        100.0 * COUNT_IF(order_status = 'Returned') / COUNT(*) AS return_rate
    FROM warehouse.vw_sales_enriched WHERE {where}
""", params).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realized revenue", compact_money(float(kpis["revenue"])))
c2.metric("Orders", f"{int(kpis['orders']):,}")
c3.metric("Customers", f"{int(kpis['customers']):,}")
c4.metric("Return rate", f"{kpis['return_rate']:.2f}%")

monthly = query(f"""
    SELECT date_trunc('month', order_date)::DATE AS month,
           SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END) AS revenue,
           COUNT(DISTINCT order_id) AS orders
    FROM warehouse.vw_sales_enriched WHERE {where}
    GROUP BY month ORDER BY month
""", params)
category = query(f"""
    SELECT category,
           SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END) AS revenue,
           100.0 * COUNT_IF(order_status = 'Returned') / COUNT(*) AS return_rate
    FROM warehouse.vw_sales_enriched WHERE {where}
    GROUP BY category ORDER BY revenue DESC
""", params)
region = query(f"""
    SELECT region, sales_channel,
           SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END) AS revenue
    FROM warehouse.vw_sales_enriched WHERE {where}
    GROUP BY region, sales_channel ORDER BY revenue DESC
""", params)
top_products = query(f"""
    SELECT product_name, category,
           SUM(CASE WHEN order_status IN ('Delivered','Shipped') THEN net_revenue ELSE 0 END) AS revenue,
           SUM(quantity) AS units
    FROM warehouse.vw_sales_enriched WHERE {where}
    GROUP BY product_name, category ORDER BY revenue DESC LIMIT 10
""", params)

left, right = st.columns([1.55, 1])
with left:
    st.plotly_chart(px.line(monthly, x="month", y="revenue", markers=True, title="Monthly realized revenue", color_discrete_sequence=["#16B8A6"]))
with right:
    st.plotly_chart(px.bar(category, x="revenue", y="category", orientation="h", title="Revenue by category", color="category", color_discrete_sequence=px.colors.qualitative.Safe))

left, right = st.columns(2)
with left:
    st.plotly_chart(px.bar(region, x="region", y="revenue", color="sales_channel", barmode="group", title="Region and channel performance"))
with right:
    st.plotly_chart(px.scatter(category, x="revenue", y="return_rate", text="category", size="revenue", title="Revenue versus return rate", color="category"))

st.subheader("Top products")
st.dataframe(
    top_products,
    width="stretch",
    hide_index=True,
    column_config={
        "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
        "units": st.column_config.NumberColumn("Units", format="%d"),
    },
)

st.divider()
st.subheader("Live order stream")
st.caption("FastAPI validates each order, RabbitMQ transports it, and the consumer writes it once to DuckDB.")


def live_order_panel() -> None:
    api_url = os.getenv("REALTIME_API_URL", "http://localhost:8000").rstrip("/")
    try:
        metrics_response = requests.get(f"{api_url}/metrics", timeout=3)
        recent_response = requests.get(f"{api_url}/orders/recent?limit=10", timeout=3)
        metrics_response.raise_for_status()
        recent_response.raise_for_status()
    except requests.RequestException:
        st.info(
            "Real-time service is offline. Start it with `docker compose up --build`, "
            "then generate events with the simulator profile."
        )
        return

    live = metrics_response.json()
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Streamed events", f"{live['total_events']:,}")
    r2.metric("Events in 60 seconds", f"{live['events_last_60_seconds']:,}")
    r3.metric("Live customers", f"{live['live_customers']:,}")
    r4.metric("Stream revenue", compact_money(float(live["live_revenue"])))

    recent = pd.DataFrame(recent_response.json())
    if recent.empty:
        st.caption("Waiting for the first order event...")
        return
    display_columns = [
        "event_time",
        "order_id",
        "category",
        "quantity",
        "net_revenue",
        "region",
        "sales_channel",
    ]
    st.dataframe(
        recent[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "event_time": "Event time (UTC)",
            "net_revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
        },
    )
    components.html(
        "<script>setTimeout(() => window.parent.location.reload(), 5000);</script>",
        height=0,
    )


live_order_panel()
