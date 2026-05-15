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
python self_check.py --adapter adapters.memora:Engine --quick
python run.py --adapter adapters.memora:Engine --mode fast \
  --seeds 9999 31415 27182 16180 11235 \
  --n-services 20 --days 14 \
  --out "$REPO_ROOT/report.json"

if [ -d "$REPO_ROOT/web/public" ]; then
  cp "$REPO_ROOT/report.json" "$REPO_ROOT/web/public/benchmark-report.json"
  echo "Copied benchmark report to web/public/benchmark-report.json"
fi
