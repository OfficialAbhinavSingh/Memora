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

- Go Context API with ingestion, reconstruction, feedback, topology alias, health, readiness, and metrics endpoints.
- ClickHouse telemetry adapter over HTTP.
- Postgres-backed topology alias, remediation feedback, and durable incident memory adapters (`incident_memories` table with JSONB signal/context, upsert on conflict).
- Optional Neo4j relationship-memory projection for aliases, incident links, causal edges, and remediation suggestions (mirrored write; bolt:// DSN).
- In-memory fallback stores for local development and tests (thread-safe, chained rename graph).
- Deterministic reconstruction: normalize → alias resolution → related event ranking → causal chain synthesis → similar incident matching → remediation ranking.
- Shape-aware incident matching using behavioral tokens (deploy, latency-spike, error-rate, upstream-failure, post-deploy-window).
- Chained rename propagation: services connected through multiple sequential renames share a canonical ID and alias set.
- Remediation feedback scoring with age decay (25% per year, floor 55%) and success/failure reinforcement.
- API validation, optional API-key auth (`PCE_API_KEY`), request size limits, structured logging, panic recovery, graceful shutdown, Prometheus-style metrics.
- Store-aware readiness checks: each configured store is pinged via `Ping() error` before the API reports ready.
- React frontend (Vite + TypeScript): 8-route SPA wired to the real reconstruction API with mock-data fallback. Routes: Incident Workspace, Incident History, Investigation Timeline, Causal Chain, Similar Incidents, Remediations, Topology Aliases, System Health.
- Pure-Python stdlib-only benchmark adapter (`bench/adapters/memora.py`) with `ingest()`, `ingest_jsonl()`, `ingest_file()`, `reconstruct_context()`, and `close()`.
- Worked-example smoke check (`bench/worked_example_check.py`) and report summarizer.
- Docker Compose infrastructure scaffold with correct DSNs: ClickHouse HTTP, Postgres, Neo4j bolt://.
- Helm/Kubernetes deployment scaffold.
- OpenAPI contract (`contracts/openapi.yaml`) with full schema for all request and response types.
- ClickHouse, Postgres, Neo4j, OTEL, Kafka, Prometheus, and ArgoCD config scaffolds.
- Example payloads and smoke script.
- Offline analysis placeholder.
- CI pipeline: gofmt, go vet, go test, go build, web lint, web build, Python syntax check, benchmark smoke, Docker build, benchmark report artifact upload.

Not yet implemented:

- Real Kafka ingestion adapter.
- Full Neo4j read path for reconstruction; Neo4j is currently a write-only mirrored projection.
- Real Redis cache adapter.
- Actual Flink streaming job code.
- End-to-end backend runtime verification on this machine (`go` and `docker` not on PATH).

## Key Files

- `README.md`: project overview, quickstart, and make targets.
- `Makefile`: `test`, `fmt`, `vet`, `run`, `web-lint`, `web-build`, `bench`, `smoke`, `docker-up`, `docker-down`.
- `services/context-api/cmd/context-api/main.go`: API process entrypoint; builds stores based on env vars.
- `services/context-api/internal/api/handler.go`: HTTP routes.
- `services/context-api/internal/api/middleware.go`: auth, logging, panic recovery, request limits.
- `services/context-api/internal/api/metrics.go`: Prometheus-style request metrics.
- `services/context-api/internal/service/engine.go`: core reconstruction logic (normalize, alias resolve, rank, causal chain, similar, remediations, confidence, explain).
- `services/context-api/internal/service/engine_test.go`: unit tests covering chained renames, rollback history, feedback reinforcement/penalty.
- `services/context-api/internal/domain/types.go`: canonical data contracts.
- `services/context-api/internal/store/interfaces.go`: storage interfaces + `MirroredGraphStore`.
- `services/context-api/internal/persistence/clickhouse`: ClickHouse telemetry adapter.
- `services/context-api/internal/persistence/postgres`: Postgres graph, feedback, and pool (pgx/v5).
- `services/context-api/internal/persistence/neo4j`: optional Neo4j projection.
- `services/context-api/internal/memory`: in-memory stores for dev and test.
- `bench/adapters/memora.py`: stdlib-only benchmark adapter with JSONL ingestion.
- `bench/worked_example_check.py`: rename-continuity end-to-end smoke check.
- `contracts/openapi.yaml`: public API contract.
- `docker-compose.yaml`: local infrastructure stack.
- `infra/postgres/schema.sql`: DDL for topology_aliases, remediation_feedback, incident_memories.
- `deploy/helm/pce`: Kubernetes/Helm chart.
- `docs/architecture.md`: architecture summary and execution paths.
- `docs/runbook.md`: operations runbook.
- `web/src/api/client.ts`: TypeScript API client aligned to the Go contract.
- `web/src/pages/IncidentWorkspace.tsx`: primary incident investigation surface, calls `/v1/context/reconstruct`.

## API Surface

- `GET /v1/health` — unauthenticated, process-level liveness
- `GET /v1/readiness` — unauthenticated, store-aware readiness
- `GET /v1/metrics` — unauthenticated, Prometheus text
- `POST /v1/ingest/events` — ingest normalized events
- `POST /v1/context/reconstruct` — reconstruct incident context
- `GET /v1/incidents/{id}/memory` — retrieve stored incident memory
- `POST /v1/feedback/remediation-outcome` — record remediation outcome
- `POST /v1/topology/alias` — register service alias

Set `PCE_API_KEY` to require `Authorization: Bearer <key>` or `X-PCE-API-Key: <key>`. Health, readiness, and metrics are always unauthenticated.

## Core Data Shape

Canonical event fields in `services/context-api/internal/domain/types.go`:

- `event_id`, `ts`, `kind`, `tenant_id`, `environment`
- `service_name`, `canonical_service_id`
- `incident_id`, `trace_id`, `entities`
- `attributes`, `raw_ref`, `provenance`

Context reconstruction returns:

- `related_events`, `causal_chain`, `similar_past_incidents`
- `suggested_remediations`, `confidence`, `explain`

## Docker Compose DSNs

```
CLICKHOUSE_DSN=http://clickhouse:8123
POSTGRES_DSN=postgres://pce:pce@postgres:5432/pce?sslmode=disable
NEO4J_URI=bolt://neo4j:7687
```

## Reconstruction Behavior

1. Normalize event timestamps and IDs.
2. Resolve canonical service identity via alias graph (chained rename-aware BFS).
3. Find related events by time window + service lineage + entity overlap.
4. Rank related events by canonical service match, incident ID, trigger match, event kind, recency.
5. Build causal edges: deploy→metric-spike (0.72), metric/trace→upstream-failure (0.68).
6. Find similar past incidents using canonical ID, trigger, behavioral shape tokens, and event kind set.
7. Rank remediations using historical feedback, canonical identity, similar incident overlap, outcome reinforcement, and age decay.
8. Score overall confidence from related event count, causal chain depth, similar incident count, and remediation count.

## Development Commands

When Go and Docker are installed:

```powershell
make test          # go test ./...
make fmt           # gofmt
make vet           # go vet
make run           # go run context-api
make web-lint      # npm run lint
make web-build     # npm run build
make bench         # python worked_example_check.py
make smoke         # bench + report
make docker-up     # docker compose up --build
```

Current environment limitation: `go` and `docker` are not on PATH. Web build, web lint, and benchmark smoke check were validated successfully.

## Next Best Implementation Step

Recommended order:

1. Redis adapter for hot-path alias and context caching.
2. Kafka consumer for event ingestion (replacing direct `/v1/ingest/events` in production).
3. Flink job for stream-time relationship synthesis.
4. Full Neo4j read path for ListIncidentMemories and alias resolution.

## Working Rules For Future Agents

- Read this file first.
- Then read only the specific files needed for the task.
- Do not re-scan the whole repo unless the task requires broad refactoring.
- Preserve the API contract in `contracts/openapi.yaml` when changing request/response shapes.
- Keep the benchmark-compatible `Context` shape intact.
- Prefer adding real adapters behind existing interfaces rather than changing API handlers.
- Keep deterministic reconstruction available even after adding ML or streaming enrichment.
- Do not remove the in-memory stores; they are required for tests and local development.
- If adding dependencies, update go.mod via `go mod tidy`, and update the relevant README, Dockerfile, and CI.
- The Neo4j URI must use `bolt://` protocol, not `http://`.
- The `incident_memories` table is the canonical durable store for reconstructed context.
