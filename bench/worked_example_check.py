import json
from adapters.memora import Engine


EVENTS = [
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


def main():
    engine = Engine()
    engine.ingest(EVENTS[:4])
    engine.reconstruct_context({
        "ts": "2026-05-10T13:30:00Z",
        "incident_id": "INC-700",
        "service": "payments-svc",
        "trigger": "alert:checkout-api/error-rate>5%",
    })
    engine.ingest(EVENTS[4:])
    context = engine.reconstruct_context({
        "ts": "2026-05-10T14:32:11Z",
        "incident_id": "INC-714",
        "service": "billing-svc",
        "trigger": "alert:checkout-api/error-rate>5%",
    })
    assert context["related_events"], "expected related events"
    assert context["causal_chain"], "expected causal chain"
    assert context["similar_past_incidents"], "expected similar incident"
    assert context["suggested_remediations"][0]["action"] == "rollback", "expected rollback"
    print(json.dumps({
        "status": "ok",
        "related_events": len(context["related_events"]),
        "causal_edges": len(context["causal_chain"]),
        "top_match": context["similar_past_incidents"][0],
        "top_remediation": context["suggested_remediations"][0],
    }, indent=2))


if __name__ == "__main__":
    main()
