from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from adapters.memora import Engine


def _ctx_without_seed_reconstruct():
    events = [
        {"ts": "2026-05-10T13:20:00Z", "kind": "deploy", "service": "payments-svc", "version": "v2.13.0"},
        {"ts": "2026-05-10T13:22:00Z", "kind": "metric", "service": "payments-svc", "name": "latency_p99_ms", "value": 4100},
        {"ts": "2026-05-10T13:30:00Z", "kind": "incident_signal", "incident_id": "INC-700", "trigger": "alert:checkout-api/error-rate>5%"},
        {"ts": "2026-05-10T13:40:00Z", "kind": "remediation", "incident_id": "INC-700", "action": "rollback", "target": "payments-svc", "version": "v2.12.9", "outcome": "resolved"},
        {"ts": "2026-05-10T14:21:30Z", "kind": "deploy", "service": "payments-svc", "version": "v2.14.0"},
        {"ts": "2026-05-10T14:22:01Z", "kind": "log", "service": "checkout-api", "level": "error", "msg": "timeout calling payments-svc", "trace_id": "abc123"},
        {"ts": "2026-05-10T14:22:01Z", "kind": "metric", "service": "payments-svc", "name": "latency_p99_ms", "value": 4820},
        {"ts": "2026-05-10T14:22:08Z", "kind": "trace", "trace_id": "abc123", "spans": [{"svc": "checkout-api", "dur_ms": 5012}, {"svc": "payments-svc", "dur_ms": 4980}]},
        {"ts": "2026-05-10T14:30:00Z", "kind": "topology", "change": "rename", "from": "payments-svc", "to": "billing-svc"},
    ]
    engine = Engine()
    engine.ingest(events)
    return engine.reconstruct_context({
        "ts": "2026-05-10T14:32:11Z",
        "incident_id": "INC-714",
        "trigger": "alert:checkout-api/error-rate>5%",
    })


def test_train_incident_is_memory_without_seed_reconstruct():
    ctx = _ctx_without_seed_reconstruct()
    assert ctx["similar_past_incidents"], ctx
    assert ctx["similar_past_incidents"][0]["past_incident_id"] == "INC-700", ctx
    assert ctx["suggested_remediations"][0]["action"] == "rollback", ctx
    assert ctx["suggested_remediations"][0]["target"] == "billing-svc", ctx


def test_rename_boundary_remaps_when_eval_service_is_known():
    ctx = _ctx_without_seed_reconstruct()
    engine = Engine()
    engine.ingest([
        {"ts": "2026-05-10T13:20:00Z", "kind": "deploy", "service": "payments-svc", "version": "v1"},
        {"ts": "2026-05-10T13:22:00Z", "kind": "metric", "service": "payments-svc", "name": "latency_p99_ms", "value": 4100},
        {"ts": "2026-05-10T13:30:00Z", "kind": "incident_signal", "incident_id": "INC-700", "trigger": "alert:checkout-api/error-rate>5%"},
        {"ts": "2026-05-10T13:40:00Z", "kind": "remediation", "incident_id": "INC-700", "action": "rollback", "target": "payments-svc", "outcome": "resolved"},
        {"ts": "2026-05-10T14:00:00Z", "kind": "topology", "change": "rename", "from": "payments-svc", "to": "billing-svc"},
        {"ts": "2026-05-10T14:21:00Z", "kind": "deploy", "service": "billing-svc", "version": "v2"},
        {"ts": "2026-05-10T14:22:00Z", "kind": "metric", "service": "billing-svc", "name": "latency_p99_ms", "value": 4820},
    ])
    ctx = engine.reconstruct_context({
        "ts": "2026-05-10T14:32:11Z",
        "incident_id": "INC-714",
        "service": "billing-svc",
        "trigger": "alert:checkout-api/error-rate>5%",
    })
    assert ctx["similar_past_incidents"][0]["past_incident_id"] == "INC-700", ctx
    assert ctx["suggested_remediations"][0]["target"] == "billing-svc", ctx


def test_chained_rename_similarity():
    engine = Engine()
    engine.ingest([
        {"ts": "2026-05-10T10:00:00Z", "kind": "deploy", "service": "payments-svc", "version": "v1"},
        {"ts": "2026-05-10T10:01:00Z", "kind": "metric", "service": "payments-svc", "name": "latency_p99_ms", "value": 2500},
        {"ts": "2026-05-10T10:05:00Z", "kind": "incident_signal", "incident_id": "INC-1", "trigger": "alert:payments-svc/latency"},
        {"ts": "2026-05-10T10:30:00Z", "kind": "remediation", "incident_id": "INC-1", "action": "rollback", "target": "payments-svc", "outcome": "worked"},
        {"ts": "2026-05-10T11:00:00Z", "kind": "topology", "change": "rename", "from": "payments-svc", "to": "billing-svc"},
        {"ts": "2026-05-10T11:05:00Z", "kind": "topology", "change": "rename", "from": "billing-svc", "to": "ledger-svc"},
        {"ts": "2026-05-10T12:00:00Z", "kind": "deploy", "service": "ledger-svc", "version": "v2"},
        {"ts": "2026-05-10T12:01:00Z", "kind": "metric", "service": "ledger-svc", "name": "latency_p99_ms", "value": 2600},
    ])
    ctx = engine.reconstruct_context({"ts": "2026-05-10T12:05:00Z", "incident_id": "INC-2", "service": "ledger-svc", "trigger": "alert:ledger-svc/latency"})
    assert ctx["similar_past_incidents"][0]["past_incident_id"] == "INC-1", ctx
    assert ctx["suggested_remediations"][0]["target"] == "ledger-svc", ctx


def test_trace_dependency_points_at_callee():
    engine = Engine()
    engine.ingest([
        {"ts": "2026-05-10T10:00:00Z", "kind": "trace", "trace_id": "t1", "spans": [{"svc": "checkout-api", "dur_ms": 100}, {"svc": "inventory-svc", "dur_ms": 2500}]},
        {"ts": "2026-05-10T10:01:00Z", "kind": "incident_signal", "incident_id": "INC-X", "trigger": "alert:checkout-api/error-rate"},
    ])
    ctx = engine.reconstruct_context({"ts": "2026-05-10T10:01:00Z", "incident_id": "INC-Y", "trigger": "alert:checkout-api/error-rate"})
    assert "inventory-svc" in ctx["explain"] or any(e.get("service_name") == "inventory-svc" or "inventory-svc" in e.get("entities", []) for e in ctx["related_events"]), ctx


def test_feedback_success_failure_and_decay():
    engine = Engine()
    engine.ingest([
        {"ts": "2025-05-10T10:00:00Z", "kind": "remediation", "incident_id": "INC-OLD", "action": "restart", "target": "api-svc", "outcome": "failed"},
        {"ts": "2026-05-10T10:00:00Z", "kind": "remediation", "incident_id": "INC-NEW", "action": "rollback", "target": "api-svc", "outcome": "worked"},
    ])
    ctx = engine.reconstruct_context({"ts": "2026-05-10T10:05:00Z", "incident_id": "INC-EVAL", "service": "api-svc", "trigger": "alert:api-svc/latency"})
    assert ctx["suggested_remediations"][0]["action"] == "rollback", ctx


def test_behavioral_shape_beats_same_service_wrong_root_cause():
    engine = Engine()
    engine.ingest([
        {"ts": "2026-05-10T09:00:00Z", "kind": "metric", "service": "ledger-svc", "name": "cpu_utilization", "value": 99},
        {"ts": "2026-05-10T09:03:00Z", "kind": "log", "service": "ledger-svc", "level": "error", "msg": "worker saturation queue overflow"},
        {"ts": "2026-05-10T09:05:00Z", "kind": "incident_signal", "incident_id": "INC-CPU", "service": "ledger-svc", "trigger": "alert:ledger-svc/error-rate"},
        {"ts": "2026-05-10T09:20:00Z", "kind": "remediation", "incident_id": "INC-CPU", "action": "scale_out", "target": "ledger-svc", "outcome": "worked"},
        {"ts": "2026-05-10T10:00:00Z", "kind": "deploy", "service": "payments-svc", "version": "v1"},
        {"ts": "2026-05-10T10:02:00Z", "kind": "metric", "service": "payments-svc", "name": "latency_p99_ms", "value": 2400},
        {"ts": "2026-05-10T10:03:00Z", "kind": "log", "service": "checkout-api", "level": "error", "msg": "timeout calling payments-svc"},
        {"ts": "2026-05-10T10:05:00Z", "kind": "incident_signal", "incident_id": "INC-LAT", "trigger": "alert:checkout-api/error-rate"},
        {"ts": "2026-05-10T10:20:00Z", "kind": "remediation", "incident_id": "INC-LAT", "action": "rollback", "target": "payments-svc", "outcome": "worked"},
        {"ts": "2026-05-10T11:00:00Z", "kind": "topology", "change": "rename", "from": "payments-svc", "to": "billing-svc"},
        {"ts": "2026-05-10T11:30:00Z", "kind": "deploy", "service": "billing-svc", "version": "v2"},
        {"ts": "2026-05-10T11:32:00Z", "kind": "metric", "service": "billing-svc", "name": "latency_p99_ms", "value": 2600},
        {"ts": "2026-05-10T11:33:00Z", "kind": "log", "service": "orders-api", "level": "error", "msg": "deadline exceeded calling billing-svc"},
    ])
    ctx = engine.reconstruct_context({"ts": "2026-05-10T11:35:00Z", "incident_id": "INC-EVAL", "service": "billing-svc", "trigger": "alert:orders-api/error-rate"})
    assert ctx["similar_past_incidents"][0]["past_incident_id"] == "INC-LAT", ctx
    assert ctx["suggested_remediations"][0]["action"] == "rollback", ctx


def test_failed_remediation_history_lowers_confidence():
    engine = Engine()
    engine.ingest([
        {"ts": "2026-05-10T10:00:00Z", "kind": "deploy", "service": "api-svc", "version": "v1"},
        {"ts": "2026-05-10T10:01:00Z", "kind": "metric", "service": "api-svc", "name": "latency_p99_ms", "value": 2500},
        {"ts": "2026-05-10T10:05:00Z", "kind": "incident_signal", "incident_id": "INC-A", "service": "api-svc", "trigger": "alert:api-svc/latency"},
        {"ts": "2026-05-10T10:15:00Z", "kind": "remediation", "incident_id": "INC-A", "action": "rollback", "target": "api-svc", "outcome": "failed"},
        {"ts": "2026-05-10T10:20:00Z", "kind": "remediation", "incident_id": "INC-A", "action": "restart", "target": "api-svc", "outcome": "worked"},
        {"ts": "2026-05-10T11:00:00Z", "kind": "deploy", "service": "api-svc", "version": "v2"},
        {"ts": "2026-05-10T11:01:00Z", "kind": "metric", "service": "api-svc", "name": "latency_p99_ms", "value": 2700},
    ])
    ctx = engine.reconstruct_context({"ts": "2026-05-10T11:05:00Z", "incident_id": "INC-B", "service": "api-svc", "trigger": "alert:api-svc/latency"})
    assert ctx["suggested_remediations"][0]["action"] == "restart", ctx
    assert ctx["suggested_remediations"][0]["confidence"] > ctx["suggested_remediations"][1]["confidence"], ctx


def test_reasoning_audit_fields_are_present():
    ctx = _ctx_without_seed_reconstruct()
    assert ctx["similar_past_incidents"][0].get("audit", {}).get("matched_behavioral_signature"), ctx
    assert ctx["causal_chain"][0].get("ordering_proof"), ctx
    assert ctx["suggested_remediations"][0].get("audit", {}).get("confidence_contributors"), ctx


def test_precision_guard_prefers_behavioral_cohort_over_family_spread():
    engine = Engine()
    events = []
    for i in range(6):
        svc = f"lat-{i}-svc"
        t = datetime(2026, 5, 10, 8, i * 5, tzinfo=timezone.utc)
        events.extend([
            {"ts": t.isoformat().replace("+00:00", "Z"), "kind": "deploy", "service": svc, "version": f"v{i}"},
            {"ts": (t + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"), "kind": "metric", "service": svc, "name": "latency_p99_ms", "value": 3200 + i},
            {"ts": (t + timedelta(minutes=3)).isoformat().replace("+00:00", "Z"), "kind": "log", "service": f"caller-{i}-api", "level": "error", "msg": f"timeout calling {svc}"},
            {"ts": (t + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), "kind": "incident_signal", "incident_id": f"INC-LAT-{i}", "service": svc, "trigger": f"alert:{svc}/latency"},
            {"ts": (t + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"), "kind": "remediation", "incident_id": f"INC-LAT-{i}", "action": "rollback", "target": svc, "outcome": "worked"},
        ])
    for i in range(6):
        svc = f"cpu-{i}-svc"
        t = datetime(2026, 5, 10, 10, i * 5, tzinfo=timezone.utc)
        events.extend([
            {"ts": t.isoformat().replace("+00:00", "Z"), "kind": "metric", "service": svc, "name": "cpu_utilization", "value": 99},
            {"ts": (t + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"), "kind": "log", "service": svc, "level": "error", "msg": "queue saturation"},
            {"ts": (t + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), "kind": "incident_signal", "incident_id": f"INC-CPU-{i}", "service": svc, "trigger": f"alert:{svc}/error-rate"},
            {"ts": (t + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"), "kind": "remediation", "incident_id": f"INC-CPU-{i}", "action": "scale_out", "target": svc, "outcome": "worked"},
        ])
    events.extend([
        {"ts": "2026-05-10T12:00:00Z", "kind": "deploy", "service": "eval-svc", "version": "v9"},
        {"ts": "2026-05-10T12:02:00Z", "kind": "metric", "service": "eval-svc", "name": "latency_p99_ms", "value": 4200},
        {"ts": "2026-05-10T12:03:00Z", "kind": "log", "service": "checkout-api", "level": "error", "msg": "timeout calling eval-svc"},
    ])
    engine.ingest(events)
    ctx = engine.reconstruct_context({"ts": "2026-05-10T12:05:00Z", "incident_id": "INC-EVAL", "service": "eval-svc", "trigger": "alert:eval-svc/latency"})
    top = ctx["similar_past_incidents"][:5]
    assert sum(1 for m in top if m["past_incident_id"].startswith("INC-LAT-")) >= 3, ctx
    assert not any(m.get("fallback_diversification") for m in top[:3]), ctx


def test_dependency_drift_matches_caller_callee_shape():
    engine = Engine()
    engine.ingest([
        {"ts": "2026-05-10T10:00:00Z", "kind": "deploy", "service": "payments-svc", "version": "v1"},
        {"ts": "2026-05-10T10:02:00Z", "kind": "metric", "service": "payments-svc", "name": "latency_p99_ms", "value": 3500},
        {"ts": "2026-05-10T10:03:00Z", "kind": "trace", "trace_id": "tr-a", "spans": [{"svc": "checkout-api", "dur_ms": 100}, {"svc": "payments-svc", "dur_ms": 3300}]},
        {"ts": "2026-05-10T10:04:00Z", "kind": "log", "service": "checkout-api", "level": "error", "msg": "timeout calling payments-svc"},
        {"ts": "2026-05-10T10:05:00Z", "kind": "incident_signal", "incident_id": "INC-DEP", "service": "payments-svc", "trigger": "alert:payments-svc/latency"},
        {"ts": "2026-05-10T10:20:00Z", "kind": "remediation", "incident_id": "INC-DEP", "action": "rollback", "target": "payments-svc", "outcome": "worked"},
        {"ts": "2026-05-10T11:00:00Z", "kind": "deploy", "service": "ledger-svc", "version": "v2"},
        {"ts": "2026-05-10T11:02:00Z", "kind": "metric", "service": "ledger-svc", "name": "latency_p99_ms", "value": 3600},
        {"ts": "2026-05-10T11:03:00Z", "kind": "trace", "trace_id": "tr-b", "spans": [{"svc": "orders-api", "dur_ms": 100}, {"svc": "ledger-svc", "dur_ms": 3400}]},
        {"ts": "2026-05-10T11:04:00Z", "kind": "log", "service": "orders-api", "level": "error", "msg": "timeout calling ledger-svc"},
    ])
    ctx = engine.reconstruct_context({"ts": "2026-05-10T11:05:00Z", "incident_id": "INC-EVAL", "service": "ledger-svc", "trigger": "alert:ledger-svc/latency"})
    assert ctx["similar_past_incidents"][0]["past_incident_id"] == "INC-DEP", ctx
    assert ctx["similar_past_incidents"][0]["shape_score"] >= 0.5, ctx


def test_fast_and_deep_latency_budget():
    engine = Engine()
    base = datetime(2026, 5, 10, tzinfo=timezone.utc)
    events = []
    for i in range(1200):
        ts = base + timedelta(seconds=i * 30)
        svc = f"svc-{i % 20}-svc"
        events.append({"ts": ts.isoformat().replace("+00:00", "Z"), "kind": "metric", "service": svc, "name": "qps", "value": i})
    events.extend([
        {"ts": "2026-05-10T10:00:00Z", "kind": "deploy", "service": "api-svc", "version": "v1"},
        {"ts": "2026-05-10T10:02:00Z", "kind": "metric", "service": "api-svc", "name": "latency_p99_ms", "value": 1200},
    ])
    engine.ingest(events)
    for mode, budget in (("fast", 2.0), ("deep", 6.0)):
        start = time.perf_counter()
        engine.reconstruct_context({"ts": "2026-05-10T10:05:00Z", "incident_id": f"INC-{mode}", "service": "api-svc", "trigger": "alert:api-svc/latency"}, mode=mode)
        elapsed = time.perf_counter() - start
        assert elapsed < budget, (mode, elapsed)


def main():
    tests = [
        test_train_incident_is_memory_without_seed_reconstruct,
        test_rename_boundary_remaps_when_eval_service_is_known,
        test_chained_rename_similarity,
        test_trace_dependency_points_at_callee,
        test_feedback_success_failure_and_decay,
        test_behavioral_shape_beats_same_service_wrong_root_cause,
        test_failed_remediation_history_lowers_confidence,
        test_reasoning_audit_fields_are_present,
        test_precision_guard_prefers_behavioral_cohort_over_family_spread,
        test_dependency_drift_matches_caller_callee_shape,
        test_fast_and_deep_latency_budget,
    ]
    for test in tests:
        test()
    print(json.dumps({"status": "ok", "tests": len(tests)}, indent=2))


if __name__ == "__main__":
    main()
