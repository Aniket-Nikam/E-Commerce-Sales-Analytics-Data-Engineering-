from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analytics import run_analytics
from .api_ingest import ingest_api_snapshot
from .benchmark import run_benchmark
from .config import RAW_CSV
from .generate_data import generate_dataset
from .pipeline import build_warehouse


def main() -> None:
    parser = argparse.ArgumentParser(description="E-commerce analytics practical")
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate")
    gen.add_argument("--rows", type=int, default=250_000)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--output", type=Path, default=RAW_CSV)

    build = commands.add_parser("build")
    build.add_argument("--input", type=Path, default=RAW_CSV)

    commands.add_parser("analyze")
    bench = commands.add_parser("benchmark")
    bench.add_argument("--runs", type=int, default=5)
    commands.add_parser("api-ingest")

    all_cmd = commands.add_parser("all")
    all_cmd.add_argument("--rows", type=int, default=250_000)
    all_cmd.add_argument("--seed", type=int, default=42)
    all_cmd.add_argument("--runs", type=int, default=5)

    args = parser.parse_args()
    if args.command == "generate":
        result = generate_dataset(args.rows, args.seed, args.output)
    elif args.command == "build":
        result = build_warehouse(args.input)
    elif args.command == "analyze":
        result = run_analytics()
    elif args.command == "benchmark":
        result = run_benchmark(args.runs)
    elif args.command == "api-ingest":
        result = ingest_api_snapshot()
    else:
        result = {
            "generation": generate_dataset(args.rows, args.seed),
            "warehouse": build_warehouse(),
            "analytics": run_analytics(),
            "benchmark": run_benchmark(args.runs),
        }
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

