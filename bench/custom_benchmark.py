"""
Memora Custom Benchmark — CORRECTED Ground-Truth Alignment
============================================================
The official generator sorts eval_signals by timestamp but does NOT sort
ground_truth, so zip(eval_signals, ground_truth) produces misaligned pairs.
This benchmark fixes the alignment by matching on incident_id instead of
relying on positional zip.

Uses the exact same scoring functions from the official metrics.py.
"""
from __future__ import annotations

import sys, os, time, json, statistics
from dataclasses import asdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bench-p02-context"))
sys.path.insert(0, os.path.join(REPO, "bench"))

from adapters.memora import Engine
from generator import GenConfig, generate, Dataset
from metrics import IncidentScore, aggregate, score_match, score_remediation
from harness import WEIGHTS, LATENCY_BUDGET_MS, compute_score
from schema import Context, IncidentSignal


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------
TIERS = [
    {
        "name": "T1 — Quick (L1/L2 baseline)",
        "seeds": [42, 101],
        "n_services": 6, "days": 2,
    },
    {
        "name": "T2 — Standard (L2 property-based)",
        "seeds": [42, 101, 202, 303, 404],
        "n_services": 12, "days": 7,
    },
    {
        "name": "T3 — Competition scale",
        "seeds": [9999, 31415, 27182, 16180, 11235],
        "n_services": 20, "days": 14,
    },
    {
        "name": "T4 — Stress / L3-preview",
        "seeds": [77777, 88888, 99999, 54321, 12345, 67890, 24680],
        "n_services": 30, "days": 21,
    },
    {
        "name": "T5 — Adversarial random seeds",
        "seeds": [314159265, 271828182, 161803398, 141421356, 173205080,
                  223606797, 264575131, 316227766, 346410161, 374165738],
        "n_services": 20, "days": 14,
    },
]


def run_tier(tier: dict, mode: str = "fast") -> dict:
    """Run a single tier with CORRECTED ground-truth alignment."""
    per_seed = []
    for seed in tier["seeds"]:
        cfg = GenConfig(seed=seed, n_services=tier["n_services"], days=tier["days"])
        engine = Engine()
        ds = generate(cfg)

        # Build incident_id → ground_truth lookup (THE FIX)
        gt_by_id = {gt["incident_id"]: gt for gt in ds.ground_truth}

        t0 = time.monotonic()
        engine.ingest(ds.train_events)
        engine.ingest(ds.eval_events)
        ingest_ms = (time.monotonic() - t0) * 1000.0

        # Warmup (2 queries, discard latency)
        for sig in ds.eval_signals[:2]:
            signal: IncidentSignal = {
                "incident_id": sig["incident_id"],
                "ts": sig["ts"],
                "trigger": sig.get("trigger", ""),
                "service": sig.get("service", ""),
            }
            engine.reconstruct_context(signal, mode=mode)

        scores: list[IncidentScore] = []
        for sig in ds.eval_signals:
            signal = {
                "incident_id": sig["incident_id"],
                "ts": sig["ts"],
                "trigger": sig.get("trigger", ""),
                "service": sig.get("service", ""),
            }

            # Match ground truth by incident_id (not position)
            gt = gt_by_id.get(sig["incident_id"])
            if gt is None:
                continue  # should never happen

            q0 = time.monotonic()
            ctx: Context = engine.reconstruct_context(signal, mode=mode)
            latency = (time.monotonic() - q0) * 1000.0

            in_top_k, precision = score_match(ctx, gt, k=5)
            rem_ok = score_remediation(ctx, gt)

            scores.append(IncidentScore(
                incident_id=sig["incident_id"],
                correct_family_in_top_k=in_top_k,
                precision_at_k=precision,
                remediation_matches=rem_ok,
                latency_ms=latency,
            ))

        summary = aggregate(scores)
        per_seed.append({
            "seed": seed,
            "n_train": len(ds.train_events),
            "n_eval": len(ds.eval_events),
            "n_signals": len(ds.eval_signals),
            "ingest_ms": round(ingest_ms, 2),
            "summary": summary,
        })
        engine.close()

    # Aggregate across seeds
    def _mean(key):
        vals = [r["summary"].get(key, 0.0) for r in per_seed if r["summary"].get("n", 0) > 0]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    n_total = sum(r["n_signals"] for r in per_seed)
    agg = {
        "recall@5":         _mean("recall@5"),
        "precision@5_mean": _mean("precision@5_mean"),
        "remediation_acc":  _mean("remediation_acc"),
        "latency_p95_ms":   round(max(r["summary"].get("latency_p95_ms", 0.0) for r in per_seed), 2),
        "latency_mean_ms":  _mean("latency_mean_ms"),
        "n_seeds":          len(per_seed),
        "n_signals_total":  n_total,
        "n":                n_total,
    }
    sc = compute_score(agg, mode)

    return {
        "tier": tier["name"],
        "config": {"n_services": tier["n_services"], "days": tier["days"], "seeds": tier["seeds"]},
        "per_seed": per_seed,
        "aggregated": agg,
        "score": sc,
    }


def main():
    mode = "fast"
    all_results = []
    grand_start = time.monotonic()

    print()
    print("=" * 72)
    print("  MEMORA BENCHMARK — CORRECTED Ground-Truth Alignment")
    print("=" * 72)
    print(f"  Mode: {mode}")
    print(f"  Tiers: {len(TIERS)}")
    print(f"  Total seeds: {sum(len(t['seeds']) for t in TIERS)}")
    print(f"  Fix: ground_truth matched by incident_id, not zip position")
    print()

    for tier in TIERS:
        t0 = time.monotonic()
        print(f"  Running: {tier['name']} ...", end="", flush=True)
        result = run_tier(tier, mode)
        elapsed = (time.monotonic() - t0) * 1000.0
        all_results.append(result)

        agg = result["aggregated"]
        sc = result["score"]
        print(f"  done ({elapsed:.0f}ms)")
        print(f"    recall@5={agg['recall@5']:.3f}  "
              f"prec@5={agg['precision@5_mean']:.3f}  "
              f"rem_acc={agg['remediation_acc']:.3f}  "
              f"lat_p95={agg['latency_p95_ms']:.1f}ms  "
              f"weighted={sc['weighted_score']:.3f}/{sc['max_automated']:.2f}")
        print()

    total_ms = (time.monotonic() - grand_start) * 1000.0

    # Summary table
    print()
    print("=" * 72)
    print("  TIER SUMMARY (CORRECTED)")
    print("=" * 72)
    print(f"  {'Tier':<40s}  {'R@5':>5s}  {'P@5':>5s}  {'Rem':>5s}  {'Lat95':>7s}  {'Score':>6s}")
    print("  " + "-" * 70)

    tier_scores = []
    for r in all_results:
        a = r["aggregated"]
        s = r["score"]
        tier_scores.append(s["weighted_score"])
        print(f"  {r['tier']:<40s}  {a['recall@5']:>5.3f}  {a['precision@5_mean']:>5.3f}  "
              f"{a['remediation_acc']:>5.3f}  {a['latency_p95_ms']:>6.1f}  "
              f"{s['weighted_score']:>6.3f}")

    print("  " + "-" * 70)
    grand_mean = statistics.mean(tier_scores)
    grand_min = min(tier_scores)
    print(f"  {'GRAND MEAN':<40s}  {'':>5s}  {'':>5s}  {'':>5s}  {'':>7s}  {grand_mean:>6.3f}")
    print(f"  {'WORST TIER':<40s}  {'':>5s}  {'':>5s}  {'':>5s}  {'':>7s}  {grand_min:>6.3f}")
    print()
    print(f"  Total wall time: {total_ms:.0f} ms")

    # Per-seed detail
    print()
    print("=" * 72)
    print("  PER-SEED DETAIL")
    print("=" * 72)
    for r in all_results:
        print(f"\n  {r['tier']}")
        print(f"  {'Seed':<12s}  {'R@5':>5s}  {'P@5':>5s}  {'Rem':>5s}  {'Lat95':>7s}  {'LatMn':>7s}  {'N':>3s}")
        print("  " + "-" * 55)
        for ps in r["per_seed"]:
            s = ps["summary"]
            print(f"  {ps['seed']:<12d}  {s['recall@5']:>5.3f}  {s['precision@5_mean']:>5.3f}  "
                  f"{s['remediation_acc']:>5.3f}  {s['latency_p95_ms']:>6.1f}  "
                  f"{s['latency_mean_ms']:>6.1f}  {s['n']:>3d}")

    # Save
    report_path = os.path.join(REPO, "corrected_benchmark_report.json")
    with open(report_path, "w") as f:
        json.dump({
            "mode": mode,
            "fix": "ground_truth matched by incident_id instead of positional zip",
            "tiers": all_results,
            "grand_mean_weighted": round(grand_mean, 4),
            "worst_tier_weighted": round(grand_min, 4),
            "total_wall_ms": round(total_ms, 1),
        }, f, indent=2)
    print(f"\n  Full report saved to: {report_path}")
    print()


if __name__ == "__main__":
    main()
