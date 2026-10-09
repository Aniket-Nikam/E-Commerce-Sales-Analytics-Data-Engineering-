from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EXTERNAL_DIR = DATA_DIR / "external"
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
RESULTS_DIR = PROJECT_ROOT / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
TABLES_DIR = RESULTS_DIR / "tables"
PLANS_DIR = RESULTS_DIR / "plans"
LOGS_DIR = RESULTS_DIR / "logs"

RAW_CSV = RAW_DIR / "ecommerce_orders.csv"
DB_PATH = ARTIFACT_DIR / "ecommerce.duckdb"
REALTIME_DB_PATH = ARTIFACT_DIR / "realtime.duckdb"
PARQUET_DIR = ARTIFACT_DIR / "sales_parquet"

RAW_COLUMNS = [
    "line_id",
    "order_id",
    "order_date",
    "customer_id",
    "customer_segment",
    "region",
    "sales_channel",
    "product_id",
    "product_name",
    "category",
    "quantity",
    "unit_price",
    "discount_pct",
    "payment_method",
    "order_status",
    "shipping_days",
]


def ensure_directories() -> None:
    for path in (
        RAW_DIR,
        EXTERNAL_DIR,
        ARTIFACT_DIR,
        RESULTS_DIR,
        CHARTS_DIR,
        TABLES_DIR,
        PLANS_DIR,
        LOGS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
