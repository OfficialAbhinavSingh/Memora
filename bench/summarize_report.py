import json
import sys


def main(path):
    with open(path, "r", encoding="utf-8") as f:
        report = json.load(f)
    if "aggregated" in report:
        agg = report.get("aggregated", {})
        score = report.get("score", {})
        for key in ["recall@5", "precision@5_mean", "remediation_acc", "latency_p95_ms", "latency_mean_ms"]:
            if key in agg:
                print(f"{key}: {agg[key]}")
        if "weighted_score" in score:
            print(f"weighted_score: {score['weighted_score']}")
        return
    for key in ["status", "related_events", "causal_edges", "top_match", "top_remediation", "note"]:
        if key in report:
            print(f"{key}: {report[key]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python bench/summarize_report.py report.json")
    main(sys.argv[1])
