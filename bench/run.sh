#!/usr/bin/env sh
set -eu

BENCH_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$BENCH_DIR")"

OFFICIAL=""
if [ -f "$REPO_ROOT/bench-p02-context/run.py" ]; then
  OFFICIAL="$REPO_ROOT/bench-p02-context"
elif [ -f "$REPO_ROOT/official-harness/bench-p02-context/run.py" ]; then
  OFFICIAL="$REPO_ROOT/official-harness/bench-p02-context"
elif [ -f "$REPO_ROOT/../bench-p02-context/run.py" ]; then
  OFFICIAL="$REPO_ROOT/../bench-p02-context"
fi

cd "$BENCH_DIR"
python worked_example_check.py
python regression_check.py

if [ -z "$OFFICIAL" ]; then
  echo "Official Anvil harness not found."
  echo "Place bench-p02-context at one of:"
  echo "  $REPO_ROOT/bench-p02-context"
  echo "  $REPO_ROOT/official-harness/bench-p02-context"
  echo "  $REPO_ROOT/../bench-p02-context"
  python local_report.py "$REPO_ROOT/report.json"
  if [ -d "$REPO_ROOT/web/public" ]; then
    cp "$REPO_ROOT/report.json" "$REPO_ROOT/web/public/benchmark-report.json"
    echo "Copied fallback report to web/public/benchmark-report.json"
  fi
  echo "Then place the official harness and rerun bench/run.sh for scored metrics."
  exit 0
fi

mkdir -p "$OFFICIAL/adapters"
cp "$BENCH_DIR/adapters/memora.py" "$OFFICIAL/adapters/memora.py"

cd "$OFFICIAL"

# Quick L2 self-check, for local iteration only (not scored).
python self_check.py --adapter adapters.memora:Engine --quick

# L3 final bench — the official submission run. Stretch config and the
# council seeds are locked inside run.py; do NOT pass --seeds /
# --n-services / --days, the harness will reject them.
REPORT_PATH="$OFFICIAL/l3_report.json"
python run.py --adapter adapters.memora:Engine --out "$REPORT_PATH"

# Mirror to repo root for convenience.
cp "$REPORT_PATH" "$REPO_ROOT/report.json"

if [ -d "$REPO_ROOT/web/public" ]; then
  cp "$REPORT_PATH" "$REPO_ROOT/web/public/benchmark-report.json"
  echo "Copied L3 report to web/public/benchmark-report.json"
fi
