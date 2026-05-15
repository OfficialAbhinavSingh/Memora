#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

echo "=== Running Smoke Check ==="
python worked_example_check.py

echo "=== Running Official Self Check ==="
python self_check.py --adapter adapters.memora:Engine --quick

echo "=== Running Full Multi-Seed Benchmark (Fast Mode) ==="
python run.py --adapter adapters.memora:Engine --mode fast --seeds 9999 31415 27182 16180 11235 --n-services 20 --days 14 --out report.json
