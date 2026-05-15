# Persistent Context Engine

Persistent Context Engine is a production-oriented scaffold for an autonomous SRE memory substrate. It provides:

- A Go context API aligned with the benchmark `Context` shape.
- A canonical telemetry envelope and normalization path.
- In-memory development implementations for telemetry, graph memory, and remediation feedback.
- Production infrastructure scaffolding for Kafka, Flink, ClickHouse, Neo4j, PostgreSQL, Redis, OpenTelemetry Collector, Helm, and ArgoCD.

## Repository layout

- `services/context-api`: Go API for ingestion, context reconstruction, feedback, and topology alias management.
- `infra/otel`: OpenTelemetry Collector configuration.
- `infra/clickhouse`: ClickHouse tables for normalized telemetry.
- `infra/postgres`: PostgreSQL schema for control-plane and feedback state.
- `infra/neo4j`: Neo4j bootstrap schema and indexes.
- `infra/argocd`: ArgoCD application manifest.
- `deploy/helm/pce`: Helm chart for the context API.
- `streaming/flink`: Flink job design contract and topic semantics.
- `contracts/openapi.yaml`: public API contract.
- `docs/architecture.md`: production architecture notes.
- `docs/runbook.md`: operational runbook and SLOs.
- `examples`: example ingest and reconstruction payloads.
- `offline`: Python utilities for offline evaluation and scoring experiments.
- `scripts/smoke.ps1`: local API smoke test.

## Context API endpoints

- `POST /v1/ingest/events`
- `POST /v1/context/reconstruct`
- `GET /v1/incidents/{id}/memory`
- `POST /v1/feedback/remediation-outcome`
- `POST /v1/topology/alias`
- `GET /v1/health`
- `GET /v1/readiness`
- `GET /v1/metrics`

## Local development

```powershell
cd services/context-api
go test ./...
go run ./cmd/context-api
```

The API defaults to `:8080`.

For a local infrastructure stack:

```powershell
docker compose up --build
```

Set `PCE_API_KEY` to require `Authorization: Bearer <key>` on mutating and incident-memory endpoints.

Example flow:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8080/v1/ingest/events -ContentType application/json -InFile examples/worked-example.json
Invoke-RestMethod -Method Post -Uri http://localhost:8080/v1/context/reconstruct -ContentType application/json -InFile examples/reconstruct-request.json
```

Or run:

```powershell
.\scripts\smoke.ps1
```

## Design notes

- The current implementation is intentionally deterministic and explainable.
- Storage adapters are interface-driven so ClickHouse, Neo4j, PostgreSQL, Redis, and Kafka-backed implementations can replace the in-memory defaults without changing handlers.
- Reconstruction already supports topology rename continuity, incident recall heuristics, causal chain synthesis, and remediation ranking using historical outcomes.
