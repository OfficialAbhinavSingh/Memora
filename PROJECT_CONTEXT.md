# Project Context: Persistent Context Engine

Read this file first before making changes. It captures the current project shape so future work can start from shared context instead of re-analyzing the whole repository.

## Product Intent

Persistent Context Engine is an autonomous SRE memory substrate. It is meant to turn operational telemetry into long-lived operational memory, not just dashboards or search results.

The core product goals are:

- Preserve operational reasoning across incidents.
- Reconstruct incident context from related historical and recent evidence.
- Recognize recurring incident shapes even when services are renamed.
- Track topology drift, causal chains, and remediation outcomes.
- Suggest historically successful remediation paths.

## Current Repo State

This repo is a production-oriented foundation, not yet a fully wired production backend.

Implemented:

- Go Context API skeleton.
- ClickHouse telemetry adapter over HTTP.
- Postgres-backed topology alias and remediation feedback adapters.
- In-memory fallback stores for local development and tests.
- Deterministic reconstruction logic.
- API validation, optional API-key auth, request limits, logging, panic recovery, graceful shutdown, and basic metrics.
- Docker Compose infrastructure scaffold.
- Helm/Kubernetes deployment scaffold.
- OpenAPI contract.
- ClickHouse, Postgres, Neo4j, OTEL, Kafka, Prometheus, and ArgoCD config scaffolds.
- Example payloads and smoke script.
- Offline analysis placeholder.

Not yet implemented:

- Real Kafka ingestion adapter.
- Real Neo4j graph-memory adapter.
- Full PostgreSQL control-plane adapter beyond aliases and remediation feedback.
- Real Redis cache adapter.
- Actual Flink streaming job code.
- End-to-end runtime verification on this machine, because `go` and `docker` were not available on PATH.

## Key Files

- `README.md`: project overview and quickstart.
- `services/context-api/cmd/context-api/main.go`: API process entrypoint.
- `services/context-api/internal/api/handler.go`: HTTP routes.
- `services/context-api/internal/api/middleware.go`: auth, logging, panic recovery, request limits.
- `services/context-api/internal/api/metrics.go`: Prometheus-style request metrics.
- `services/context-api/internal/service/engine.go`: core reconstruction and memory logic.
- `services/context-api/internal/domain/types.go`: public data contracts used by the API.
- `services/context-api/internal/store/interfaces.go`: storage interfaces to replace in-memory stores.
- `services/context-api/internal/persistence/clickhouse`: real telemetry persistence adapter.
- `services/context-api/internal/persistence/postgres`: real Postgres alias and feedback adapters.
- `services/context-api/internal/memory`: in-memory development store implementations.
- `services/context-api/internal/service/engine_test.go`: current unit tests for rename-aware reconstruction.
- `contracts/openapi.yaml`: public API contract.
- `docker-compose.yaml`: local infrastructure stack.
- `deploy/helm/pce`: Kubernetes/Helm chart.
- `docs/architecture.md`: architecture summary.
- `docs/runbook.md`: operations runbook.
- `streaming/flink/README.md`: Flink job contract.

## API Surface

The API exposes:

- `GET /v1/health`
- `GET /v1/readiness`
- `GET /v1/metrics`
- `POST /v1/ingest/events`
- `POST /v1/context/reconstruct`
- `GET /v1/incidents/{id}/memory`
- `POST /v1/feedback/remediation-outcome`
- `POST /v1/topology/alias`

Set `PCE_API_KEY` to require either:

- `Authorization: Bearer <key>`
- `X-PCE-API-Key: <key>`

Health, readiness, and metrics endpoints remain unauthenticated.

## Core Data Shape

Canonical event fields live in `services/context-api/internal/domain/types.go`.

Important fields:

- `event_id`
- `ts`
- `kind`
- `tenant_id`
- `environment`
- `service_name`
- `canonical_service_id`
- `incident_id`
- `trace_id`
- `entities`
- `attributes`
- `raw_ref`
- `provenance`

Context reconstruction returns:

- `related_events`
- `causal_chain`
- `similar_past_incidents`
- `suggested_remediations`
- `confidence`
- `explain`

## Current Architecture Decision

The chosen production stack is:

- OpenTelemetry Collector for telemetry intake.
- Kafka for durable event streaming and replay.
- Flink for stateful online memory formation.
- ClickHouse for high-volume telemetry lookup.
- Neo4j for long-horizon operational relationship memory.
- PostgreSQL for control-plane and feedback state.
- Redis for fast-mode cache and hot aliases.
- S3-compatible object storage for archives and replay bundles.
- Go for the online API.
- Python for offline analysis.
- Kubernetes, Helm, and ArgoCD for deployment.

## Reconstruction Behavior Today

The current Go engine:

- Normalizes incoming events.
- Stores topology rename aliases from topology events or alias API calls.
- Resolves canonical service IDs.
- Finds related events by time window, service lineage, entities, and attributes.
- Builds causal edges for deploy-to-metric-spike and metric/trace-to-failure sequences.
- Stores reconstructed incident memory.
- Finds similar past incidents using deterministic weighted similarity.
- Ranks remediations using historical feedback and canonical service identity.

This is a deterministic baseline, not the final streaming production intelligence layer.

## Development Commands

Expected commands when Go and Docker are installed:

```powershell
cd services/context-api
go test ./...
go run ./cmd/context-api
```

From repo root:

```powershell
docker compose up --build
.\scripts\smoke.ps1
```

Current environment limitation:

- `go` was not available on PATH.
- `docker` was not available on PATH.
- JSON examples were validated successfully with the bundled Python runtime.

## Next Best Implementation Step

The highest-value next engineering step is to add real storage adapters behind `services/context-api/internal/store/interfaces.go`.

Recommended order:

1. PostgreSQL adapter for remediation feedback and topology aliases.
2. ClickHouse adapter for event storage and related-event lookup.
3. Neo4j adapter for alias lineage and incident memory graph.
4. Redis adapter for fast context and alias cache.
5. Kafka producer/consumer path for ingestion and memory events.
6. Flink job implementation for stream-time relationship synthesis.

## Working Rules For Future Agents

- Read this file first.
- Then read only the specific files needed for the task.
- Do not re-scan the whole repo unless the task requires broad refactoring or unknown ownership.
- Preserve the API contract in `contracts/openapi.yaml` when changing request/response shapes.
- Keep the benchmark-compatible `Context` shape intact.
- Prefer adding real adapters behind existing interfaces rather than changing API handlers.
- Keep deterministic reconstruction available even after adding ML or streaming enrichment.
- Do not remove the in-memory stores; they are useful for tests and local development.
- If adding dependencies, update the relevant README, Dockerfile, and CI workflow.
