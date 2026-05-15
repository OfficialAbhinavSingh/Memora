#!/usr/bin/env python3
import json
import sys
from statistics import mean


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: summarize_report.py <report.json>", file=sys.stderr)
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        report = json.load(handle)

    contexts = report if isinstance(report, list) else report.get("contexts", [])
    confidences = [float(item.get("confidence", 0)) for item in contexts]
    causal_edges = [len(item.get("causal_chain", [])) for item in contexts]
    matches = [len(item.get("similar_past_incidents", [])) for item in contexts]
    remediations = [len(item.get("suggested_remediations", [])) for item in contexts]

    summary = {
        "contexts": len(contexts),
        "confidence_mean": round(mean(confidences), 4) if confidences else 0,
        "causal_edges_mean": round(mean(causal_edges), 4) if causal_edges else 0,
        "similar_matches_mean": round(mean(matches), 4) if matches else 0,
        "remediation_suggestions_mean": round(mean(remediations), 4) if remediations else 0,
    }

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
