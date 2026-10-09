from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import RAW_CSV, ensure_directories


CATEGORIES = {
    "Electronics": [
        ("Wireless Earbuds", 79.0), ("Smart Watch", 145.0),
        ("Bluetooth Speaker", 92.0), ("USB-C Hub", 54.0),
        ("Mechanical Keyboard", 118.0), ("Web Camera", 68.0),
        ("Tablet", 325.0), ("Gaming Mouse", 61.0),
    ],
    "Home": [
        ("Air Fryer", 132.0), ("Desk Lamp", 39.0),
        ("Vacuum Cleaner", 189.0), ("Coffee Maker", 96.0),
        ("Storage Rack", 75.0), ("Bedsheet Set", 44.0),
        ("Water Purifier", 215.0), ("Cookware Set", 119.0),
    ],
    "Fashion": [
        ("Running Shoes", 89.0), ("Denim Jacket", 74.0),
        ("Cotton Shirt", 42.0), ("Handbag", 97.0),
        ("Analog Watch", 110.0), ("Sunglasses", 58.0),
        ("Backpack", 66.0), ("Casual Trousers", 48.0),
    ],
    "Beauty": [
        ("Skin Serum", 34.0), ("Hair Dryer", 55.0),
        ("Perfume", 82.0), ("Face Cleanser", 22.0),
        ("Makeup Kit", 63.0), ("Body Lotion", 19.0),
        ("Trimmer", 47.0), ("Sunscreen", 25.0),
    ],
    "Sports": [
        ("Yoga Mat", 31.0), ("Cricket Bat", 86.0),
        ("Dumbbell Set", 105.0), ("Football", 29.0),
        ("Fitness Band", 72.0), ("Cycling Helmet", 59.0),
        ("Badminton Racket", 49.0), ("Sports Bottle", 18.0),
    ],
    "Books": [
        ("Data Engineering Handbook", 41.0), ("SQL Practice Guide", 32.0),
        ("Python for Analytics", 38.0), ("Business Storytelling", 29.0),
        ("Statistics Workbook", 35.0), ("Cloud Fundamentals", 44.0),
        ("Machine Learning Primer", 47.0), ("Product Management", 31.0),
    ],
}


def generate_dataset(rows: int, seed: int, output: Path = RAW_CSV) -> dict:
    ensure_directories()
    rng = np.random.default_rng(seed)

    catalog = []
    product_number = 1
    for category, products in CATEGORIES.items():
        for name, price in products:
            catalog.append((f"P{product_number:04d}", name, category, price))
            product_number += 1
    catalog_df = pd.DataFrame(
        catalog, columns=["product_id", "product_name", "category", "base_price"]
    )

    product_index = rng.choice(len(catalog_df), size=rows, replace=True)
    selected = catalog_df.iloc[product_index].reset_index(drop=True)

    order_count = max(1, int(rows / 2.1))
    order_pool = np.array([f"O{i:08d}" for i in range(1, order_count + 1)])
    order_assignment = np.arange(rows) % order_count
    rng.shuffle(order_assignment)
    order_ids = order_pool[order_assignment]
    line_ids = np.array([f"L{i:09d}" for i in range(1, rows + 1)])

    customer_count = max(500, int(order_count / 3.0))
    customer_pool = np.array([f"C{i:06d}" for i in range(1, customer_count + 1)])
    popularity = np.arange(1, customer_count + 1, dtype=float) ** -0.25
    popularity /= popularity.sum()
    order_customer_index = rng.choice(customer_count, size=order_count, p=popularity)
    order_customer_ids = customer_pool[order_customer_index]
    customer_ids = order_customer_ids[order_assignment]

    start = np.datetime64("2024-01-01")
    end = np.datetime64("2026-01-01")
    day_offsets = rng.integers(0, int((end - start) / np.timedelta64(1, "D")), order_count)
    dates = start + day_offsets.astype("timedelta64[D]")
    hours = rng.integers(0, 24, order_count).astype("timedelta64[h]")
    minutes = rng.integers(0, 60, order_count).astype("timedelta64[m]")
    order_dates = (dates.astype("datetime64[m]") + hours + minutes)[order_assignment]

    quantities = rng.choice([1, 2, 3, 4, 5, 6], size=rows, p=[0.48, 0.26, 0.13, 0.07, 0.04, 0.02])
    price_noise = rng.normal(1.0, 0.07, rows)
    unit_prices = np.round(selected["base_price"].to_numpy() * price_noise, 2)
    discounts = rng.choice([0, 5, 10, 15, 20, 25, 30], size=rows, p=[0.23, 0.17, 0.23, 0.15, 0.12, 0.07, 0.03])

    customer_regions = rng.choice(["North", "South", "East", "West", "Central"], size=customer_count, p=[0.21, 0.23, 0.2, 0.22, 0.14])
    customer_segments = rng.choice(["Consumer", "Corporate", "Small Business"], size=customer_count, p=[0.72, 0.15, 0.13])
    regions = customer_regions[order_customer_index][order_assignment]
    segments = customer_segments[order_customer_index][order_assignment]
    channels = rng.choice(["Web", "Mobile App", "Marketplace"], size=order_count, p=[0.42, 0.39, 0.19])[order_assignment]
    payments = rng.choice(["UPI", "Card", "Wallet", "Cash on Delivery"], size=order_count, p=[0.34, 0.33, 0.15, 0.18])[order_assignment]
    order_statuses = rng.choice(["Delivered", "Shipped", "Returned", "Cancelled"], size=order_count, p=[0.78, 0.1, 0.07, 0.05])
    statuses = order_statuses[order_assignment]
    order_shipping_days = np.where(order_statuses == "Cancelled", 0, rng.integers(1, 11, order_count))
    shipping_days = order_shipping_days[order_assignment]

    df = pd.DataFrame({
        "line_id": line_ids,
        "order_id": order_ids,
        "order_date": pd.to_datetime(order_dates).strftime("%Y-%m-%d %H:%M:%S"),
        "customer_id": customer_ids,
        "customer_segment": segments,
        "region": regions,
        "sales_channel": channels,
        "product_id": selected["product_id"],
        "product_name": selected["product_name"],
        "category": selected["category"],
        "quantity": quantities.astype(object),
        "unit_price": unit_prices.astype(object),
        "discount_pct": discounts.astype(object),
        "payment_method": payments,
        "order_status": statuses,
        "shipping_days": shipping_days.astype(object),
    })

    # Intentional defects for the cleaning exercise.
    defect_sets = {
        "missing_customer": rng.choice(rows, max(1, rows // 500), replace=False),
        "missing_price": rng.choice(rows, max(1, rows // 650), replace=False),
        "invalid_quantity": rng.choice(rows, max(1, rows // 800), replace=False),
        "invalid_discount": rng.choice(rows, max(1, rows // 1000), replace=False),
        "dirty_region": rng.choice(rows, max(1, rows // 60), replace=False),
        "dirty_category": rng.choice(rows, max(1, rows // 80), replace=False),
    }
    df.loc[defect_sets["missing_customer"], "customer_id"] = None
    df.loc[defect_sets["missing_price"], "unit_price"] = None
    df.loc[defect_sets["invalid_quantity"], "quantity"] = -3
    df.loc[defect_sets["invalid_discount"], "discount_pct"] = 140
    df.loc[defect_sets["dirty_region"], "region"] = " north "
    df.loc[defect_sets["dirty_category"], "category"] = df.loc[
        defect_sets["dirty_category"], "category"
    ].str.lower()

    duplicate_count = max(1, rows // 1000)
    duplicates = df.sample(duplicate_count, random_state=seed)
    final_df = pd.concat([df, duplicates], ignore_index=True)
    final_df = final_df.sample(frac=1, random_state=seed).reset_index(drop=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output, index=False)
    metadata = {
        "output": str(output),
        "requested_rows": rows,
        "written_rows": int(len(final_df)),
        "duplicate_rows_injected": duplicate_count,
        "seed": seed,
        "date_min": str(final_df["order_date"].min()),
        "date_max": str(final_df["order_date"].max()),
    }
    output.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=250_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=RAW_CSV)
    args = parser.parse_args()
    print(json.dumps(generate_dataset(args.rows, args.seed, args.output), indent=2))


if __name__ == "__main__":
    main()
