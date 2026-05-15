import json
import sys


def main(path):
    with open(path, "r", encoding="utf-8") as f:
        report = json.load(f)
    keys = ["recall@5", "precision@5_mean", "remediation_acc", "latency_p95", "weighted_score"]
    printed = False
    for key in keys:
        value = report.get(key)
        if value is not None:
            print(f"{key}: {value}")
            printed = True
    if not printed:
        for key in ["status", "related_events", "causal_edges", "top_match", "top_remediation"]:
            if key in report:
                print(f"{key}: {report[key]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python bench/summarize_report.py report.json")
    main(sys.argv[1])
