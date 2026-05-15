# Flink job contract

This repository currently ships the serving plane and storage contracts. The streaming layer is expected to publish and consume the following topics:

- `telemetry.raw`
- `telemetry.normalized`
- `topology.events`
- `incident.signals`
- `memory.edges`
- `memory.patterns`
- `remediation.events`
- `feedback.events`

## Job stages

1. Normalize raw OTEL and non-OTEL telemetry into the canonical event envelope.
2. Resolve service identities and topology aliases keyed by `tenant_id + environment`.
3. Synthesize temporal and causal edges from deploy, metric, log, trace, incident, and remediation windows.
4. Emit durable memory edges for Neo4j and normalized facts for ClickHouse.
5. Publish incident fingerprints for family matching and remediation learning.

## Canonical event envelope

```json
{
  "event_id": "evt-123",
  "ts": "2026-05-10T14:22:01Z",
  "kind": "metric",
  "tenant_id": "tenant-a",
  "environment": "prod",
  "service_name": "payments-svc",
  "canonical_service_id": "svc:billing-svc",
  "incident_id": "INC-714",
  "trace_id": "abc123",
  "entities": ["payments-svc", "checkout-api"],
  "attributes": {"name": "latency_p99_ms", "value": 4820},
  "raw_ref": "s3://telemetry/2026/05/10/evt-123.json",
  "provenance": {"source": "otel", "cluster": "prod-a"}
}
```

## Production hand-off

The Flink implementation should use the same envelope and relationship semantics as the Go API so offline and online paths agree on:

- canonical service resolution
- incident-family fingerprints
- remediation confidence updates
- explainable evidence pointers
