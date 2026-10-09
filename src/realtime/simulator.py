from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.config import RESULTS_DIR, ensure_directories

CATEGORIES = {
    "Electronics": (80, 1500),
    "Fashion": (15, 240),
    "Home": (25, 700),
    "Sports": (12, 450),
    "Beauty": (8, 180),
    "Books": (5, 80),
}
REGIONS = ["North", "South", "East", "West"]
CHANNELS = ["Web", "Mobile App", "Marketplace"]


def make_event(rng: random.Random, sequence: int) -> dict:
    category = rng.choice(list(CATEGORIES))
    low, high = CATEGORIES[category]
    return {
        "event_time": datetime.now(timezone.utc).isoformat(),
        "order_id": f"LIVE-{int(time.time())}-{sequence:05d}",
        "customer_id": f"C{rng.randint(1, 50000):06d}",
        "product_id": f"P{rng.randint(1, 48):03d}",
        "category": category,
        "quantity": rng.randint(1, 5),
        "unit_price": round(rng.uniform(low, high), 2),
        "discount_pct": rng.choice([0, 0, 0.05, 0.10, 0.15]),
        "region": rng.choice(REGIONS),
        "sales_channel": rng.choice(CHANNELS),
    }


def run(api_url: str, events: int, interval: float, seed: int) -> dict:
    rng = random.Random(seed)
    accepted = 0
    failed = 0
    started = datetime.now(timezone.utc)
    sequence = 1
    while events == 0 or sequence <= events:
        try:
            response = requests.post(
                f"{api_url.rstrip('/')}/orders",
                json=make_event(rng, sequence),
                timeout=10,
            )
            response.raise_for_status()
            accepted += 1
        except requests.RequestException:
            failed += 1
        sequence += 1
        time.sleep(interval)
    summary = {
        "api_url": api_url,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "requested_events": events,
        "accepted_events": accepted,
        "failed_events": failed,
        "interval_seconds": interval,
    }
    ensure_directories()
    (RESULTS_DIR / "realtime_demo.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate live e-commerce order events")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--events", type=int, default=50, help="Use 0 to run continuously")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(run(args.api_url, args.events, args.interval, args.seed), indent=2))


if __name__ == "__main__":
    main()

