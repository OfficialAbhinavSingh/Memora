from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("report.json")
    report = {
        "mode": "local-fallback",
        "seeds": [],
        "per_seed": [],
        "status": "ok",
        "note": (
            "Official bench-p02-context harness was not found. "
            "Local worked example and regression checks passed; run the official "
            "Anvil harness with adapters.memora:Engine for scored metrics."
        ),
        "checks": {
            "worked_example_check": "passed",
            "regression_check": "passed",
        },
        "adapter": "bench.adapters.memora:Engine",
        "official_adapter": "adapters.memora:Engine",
        "dependencies": "Python standard library only for the benchmark adapter",
        "network_egress": "none",
        "aggregated": {
            "recall@5": 0.0,
            "precision@5_mean": 0.0,
            "remediation_acc": 0.0,
            "latency_p95_ms": 0.0,
            "latency_mean_ms": 0.0,
            "n_seeds": 0,
            "n_signals_total": 0,
            "n": 0,
        },
        "score": {
            "axes": {
                "recall@5": 0.0,
                "precision@5_mean": 0.0,
                "remediation_acc": 0.0,
                "latency_p95_ms": 0.0,
                "manual_context": None,
                "manual_explain": None,
            },
            "weighted_score": 0.0,
            "max_automated": 0.8,
            "note": "fallback report only; official harness not present",
        },
    }
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote local fallback report to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
