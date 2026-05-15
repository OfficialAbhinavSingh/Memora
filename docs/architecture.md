# Persistent Context Engine Architecture

## Product goal

The engine turns operational telemetry into persistent memory. It should reconstruct incident context, identify recurring incident shapes, survive service renames, and learn which remediations worked historically.

## Runtime flow

1. OpenTelemetry Collector receives logs, metrics, traces, deploys, topology events, and incident signals.
2. Kafka preserves the event stream and enables replay.
3. Flink normalizes events, resolves service identity, synthesizes relationships, and emits memory edges.
4. ClickHouse stores high-volume telemetry for fast time-window lookup.
5. Neo4j stores long-horizon relationships such as aliases, causal edges, incident families, and remediation paths.
6. PostgreSQL stores control-plane records, manual overrides, annotations, and feedback.
7. Redis caches hot aliases, recent context, and fast-mode incident-family hints.
8. The Go API reconstructs structured context for responders.
9. S3-compatible storage archives raw events, replay bundles, snapshots, and offline evaluation data.

## Execution paths

- Benchmark path: `bench.adapters.memora:Engine` runs as a pure-Python, stdlib-only adapter for the public harness. It normalizes JSONL benchmark events, preserves provenance, and reconstructs the required structured `Context` without requiring Docker or network access.
- Production API path: `services/context-api` exposes HTTP ingestion, context reconstruction, feedback, topology aliases, health, readiness, and metrics for operators and the web UI.
- Durable store path: ClickHouse stores normalized telemetry, PostgreSQL stores aliases, remediation feedback, and incident memories, and Neo4j receives mirrored relationship projections for aliases, incident similarity, causal edges, and remediation links.
- Streaming path: Kafka and Flink remain the intended online synthesis layer for higher-throughput relationship formation; the deterministic API engine remains available as the explainable reconstruction core.

## First production milestone

The current codebase implements the Go API, deterministic reconstruction logic, development stores, ClickHouse telemetry persistence, PostgreSQL durable control-plane and incident memory persistence, Neo4j relationship projection, deployment manifests, and infrastructure contracts. The next implementation milestone is Kafka/Flink stream-time synthesis and Redis hot-path caching.

## Operational guarantees

- Fast context reconstruction is designed around a short recent window and cached identity hints.
- Deep context reconstruction widens the event window and graph traversal.
- Every related event and causal edge should preserve evidence pointers.
- Service aliases are first-class memory, not a string replacement trick.
- Feedback reinforces remediation confidence without deleting contradictory history.
- Readiness checks configured stores; health remains process-level.
