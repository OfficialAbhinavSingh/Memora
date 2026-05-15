# Persistent Context Engine Runbook

## Readiness checks

- `GET /v1/health` confirms the API process is alive.
- `GET /v1/readiness` confirms the API is ready for traffic.
- `GET /v1/metrics` exposes request counts and latency sums in Prometheus text format.

## Normal operation

1. Send normalized telemetry to `POST /v1/ingest/events`.
2. Record topology renames with `POST /v1/topology/alias` or topology events.
3. Record remediation outcomes with `POST /v1/feedback/remediation-outcome`.
4. Reconstruct incident context with `POST /v1/context/reconstruct`.

## Incident response for the engine

- If reconstruction is slow, check API CPU, ClickHouse query latency, Redis hit rate, and Neo4j traversal latency.
- If similar incidents disappear after renames, check topology alias ingestion and canonical service IDs.
- If remediation suggestions are weak, check whether successful remediation feedback is being recorded.
- If context is noisy, lower the fast-mode window or raise confidence thresholds in the reconstruction scorer.

## SLOs

- Ingest lag: under 5 seconds.
- Fast reconstruction p95: under 2 seconds.
- Deep reconstruction p95: under 6 seconds.
- API availability: 99.9% for reconstruction endpoints.

## Recovery

- Replay raw Kafka or S3 archives to rebuild ClickHouse and memory graph state.
- Restore Postgres first for control-plane state, then Neo4j for relationship memory, then ClickHouse for telemetry windows.
- Keep topology alias overrides as durable control-plane data so identity continuity survives rebuilds.
