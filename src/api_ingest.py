from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from .config import EXTERNAL_DIR, ensure_directories
from .pipeline import load_api_snapshot

BASE_URL = "https://dummyjson.com"


def _get_json(resource: str) -> dict:
    request = Request(
        f"{BASE_URL}/{resource}",
        headers={"User-Agent": "ecommerce-duckdb-case-study/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def ingest_api_snapshot(output_dir: Path = EXTERNAL_DIR) -> dict:
    ensure_directories()
    output_dir.mkdir(parents=True, exist_ok=True)
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    products = _get_json("products?limit=0")
    carts = _get_json("carts?limit=0")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = output_dir / f"dummyjson_snapshot_{stamp}.json"
    raw_path.write_text(
        json.dumps({"observed_at_utc": observed_at, "products": products, "carts": carts}, indent=2),
        encoding="utf-8",
    )

    product_map = {int(p["id"]): p for p in products.get("products", [])}
    rows = []
    for cart in carts.get("carts", []):
        for item in cart.get("products", []):
            product = product_map.get(int(item["id"]), {})
            rows.append({
                "observed_at_utc": observed_at,
                "cart_id": cart["id"],
                "user_id": cart["userId"],
                "product_id": item["id"],
                "product_title": item.get("title", product.get("title")),
                "category": product.get("category", "unknown"),
                "brand": product.get("brand", "unknown"),
                "quantity": item.get("quantity"),
                "unit_price": item.get("price"),
                "discount_pct": item.get("discountPercentage"),
                "line_total": item.get("total"),
                "discounted_total": item.get("discountedTotal", item.get("discountedPrice")),
            })

    csv_path = output_dir / "dummyjson_cart_items_latest.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    loaded_rows = load_api_snapshot(csv_path)
    metadata = {
        "source": BASE_URL,
        "observed_at_utc": observed_at,
        "products": len(product_map),
        "carts": len(carts.get("carts", [])),
        "flattened_cart_items": len(rows),
        "loaded_to_duckdb": loaded_rows,
        "raw_json": str(raw_path),
        "csv": str(csv_path),
    }
    (output_dir / "api_ingestion_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata

