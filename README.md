# E-Commerce Sales Analytics using DuckDB

This practical case study implements a local analytical data platform with Python, SQL, DuckDB, CSV, Parquet, Streamlit, a public e-commerce API, Docker, and Kubernetes manifests.

![Streamlit analytics dashboard](evidence/dashboard_full.png)

## Submission deliverables

- [Case study report (PDF)](docs/ECommerce_Sales_Analytics_DuckDB_Report.pdf)
- [Presentation deck (10 slides)](docs/ECommerce_DuckDB_Case_Study_Presentation.pptx)
- [Captured charts, KPI tables, query plans, and API metadata](evidence/)
- Reproducible Python/SQL source code, test, Dockerfile, and Kubernetes manifests

## Practical-guideline coverage

| Requirement from the brief | Implementation evidence |
|---|---|
| Set up Python environment | Pinned `requirements.txt`, quick-start commands, Windows/Linux launchers |
| Load CSV / JSON / API | Generated CSV plus a current DummyJSON products-and-carts API snapshot |
| Perform data processing | DuckDB cleaning, validation, rejection handling, and a star schema |
| Apply transformations and actions | Derived revenue fields, dimensions, KPI views, joins, windows, CUBE, ROLLUP, and GROUPING SETS |
| Optimize performance | ZSTD Parquet partitions, DuckDB indexes, thread controls, and `EXPLAIN ANALYZE` plans |
| Capture results | Versioned dashboard screenshot, plots, KPI JSON/CSV, and plans in `evidence/` |
| Analyze performance | CSV vs Parquet vs DuckDB benchmark at 1 and 4 threads |
| Report, code, and PPT | PDF report, documented source code, and a 10-slide presentation |
| Bonus: real-time dataset / API | Public API ingestion command and captured snapshot metadata |
| Bonus: Kubernetes | Deployment, Service, PVC, probes, HPA, and Kustomize configuration |
| Bonus: compare execution modes | Storage-format and thread-count benchmark with an explicitly stated local-OLAP scope |

## What the project demonstrates

- Generates a reproducible e-commerce CSV containing realistic data-quality defects.
- Cleans types, nulls, duplicates, invalid ranges, and inconsistent categories in DuckDB SQL.
- Models a star schema with `fact_sales`, `dim_customer`, `dim_product`, and `dim_date`.
- Creates reusable KPI views for revenue, monthly growth, repeat customers, and returns.
- Runs joins, aggregations, windows, `ROLLUP`, `CUBE`, and `GROUPING SETS`.
- Exports partitioned ZSTD Parquet and records `EXPLAIN ANALYZE` plans.
- Benchmarks CSV, partitioned Parquet, and DuckDB tables with 1 and 4 threads.
- Builds a Streamlit dashboard with filters and decision-focused charts.
- Ingests a current public API snapshot from DummyJSON as a bonus extension.
- Includes a container image and Kubernetes deployment, service, PVC, probes, and HPA.

## Quick start

Create and activate a Python 3.11+ virtual environment, then run:

```bash
pip install -r requirements.txt
python -m src.cli all --rows 250000
streamlit run src/dashboard.py
```

Open `http://localhost:8501`.

The `all` command writes the generated CSV to `data/raw`, the DuckDB database and Parquet dataset to `artifacts`, and charts, query outputs, logs, and benchmark evidence to `results`.

## Commands

```bash
python -m src.cli generate --rows 250000 --seed 42
python -m src.cli build
python -m src.cli analyze
python -m src.cli benchmark --runs 5
python -m src.cli api-ingest
python -m src.cli all --rows 250000
```

Use a different input file:

```bash
python -m src.cli build --input path/to/orders.csv
```

The replacement CSV should contain the columns listed in `src/config.py` under `RAW_COLUMNS`.

## Dashboard questions

1. How are revenue and order volume changing by month?
2. Which categories produce the most realized revenue?
3. Which regions and channels are underperforming?
4. Which categories have the highest return rate?
5. How concentrated is revenue among the top customers?

## Bonus work

### Public API snapshot

```bash
python -m src.cli api-ingest
```

This calls the DummyJSON products and carts endpoints, preserves the raw JSON response, flattens cart items to CSV, and loads the snapshot into the DuckDB table `api_cart_items` when the database exists.

### Kubernetes

```bash
docker build -t ecommerce-duckdb:1.0 .
kubectl apply -k kubernetes/
kubectl -n ecommerce-analytics port-forward svc/ecommerce-duckdb 8501:80
```

The Deployment uses Streamlit's health endpoint for startup, readiness, and liveness probes. The PVC persists the DuckDB database and generated artifacts. The HPA requires the Kubernetes Metrics Server.

### Performance modes

The benchmark varies both storage format and DuckDB thread count. DuckDB is an in-process OLAP database, so these are scale-up execution modes rather than distributed cluster modes. The comparison remains directly relevant to the selected DuckDB case-study topic.

## Project structure

```text
src/                 Python pipeline, analytics, benchmark, API, dashboard, CLI
sql/                 Schema, views, analytical SQL, and OLAP patterns
tests/               Reproducible smoke test
kubernetes/          Kubernetes manifests and Kustomize file
data/                 Generated or API source data (created at runtime)
artifacts/            DuckDB and partitioned Parquet (created at runtime)
results/              Query outputs, plots, plans, metrics, and logs
evidence/             Curated, version-controlled output evidence
docs/                 Final report and presentation
```

## Data note

The core dataset is synthetic and deterministic so the implementation runs without credentials or a large download. It intentionally contains missing values, duplicates, invalid quantities, and inconsistent text values. The API extension provides current public e-commerce data for the bonus requirement. Neither dataset represents a real company's financial results.
