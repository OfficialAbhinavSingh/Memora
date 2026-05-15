# Persistent Context Engine

Persistent Context Engine is a production-oriented scaffold for an autonomous SRE memory substrate. It provides:

- A Go context API aligned with the benchmark `Context` shape.
- A canonical telemetry envelope and normalization path.
- Real ClickHouse telemetry persistence, Postgres-backed aliases/feedback/incident memory, and optional Neo4j relationship projection, with in-memory fallbacks for development and tests.
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
- `bench`: stdlib-only benchmark adapter and worked-example check.
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

Useful `make` targets (require Go and Docker on PATH):

| Command | Action |
|---------|--------|
| `make test` | Run Go unit tests |
| `make fmt` | gofmt all Go files |
| `make vet` | go vet |
| `make run` | Run the context API locally |
| `make web-lint` | Lint the React frontend |
| `make web-build` | Production build of the frontend |
| `make web-docker` | Build the Nginx+React production Docker image |
| `make bench` | Run the Python worked-example smoke check |
| `make docker-up` | Start the full local stack |
| `make docker-down` | Stop the local stack |

Backend:

```powershell
cd services/context-api
go test ./...
go run ./cmd/context-api
```

The API defaults to `:8080`.

Frontend:

```powershell
cd web
npm install
npm run dev
npm run build
```

Benchmark adapter smoke check:

```powershell
python bench\worked_example_check.py
```

The adapter is `bench.adapters.memora:Engine` and exposes the benchmark surface:

- `ingest(events)`
- `reconstruct_context(signal, mode="fast")`
- `close()`

For a local infrastructure stack:

```powershell
docker compose up --build
```

Docker Compose wires the API to ClickHouse, Postgres, and Neo4j using:

- `CLICKHOUSE_DSN=http://clickhouse:8123`
- `POSTGRES_DSN=postgres://pce:pce@postgres:5432/pce?sslmode=disable`
- `NEO4J_URI=bolt://neo4j:7687`

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
- Storage adapters are interface-driven. ClickHouse stores telemetry, Postgres stores control-plane state and incident memory, and Neo4j receives mirrored relationship projections.
- Reconstruction supports topology rename continuity, shape-aware incident recall, causal chain synthesis, and remediation ranking using historical outcomes with feedback decay.
- External AI, embedding, and LLM services are not required and no outbound provider egress is used by default.

## Frontend deployment

Two supported models:

### Same-domain Nginx (default — no CORS)

`docker compose up` starts a `web-ui` container that runs Nginx on port 3000.
Nginx serves `web/dist/` at `/` and reverse-proxies `/v1/*` to `context-api:8080`
on the internal Docker network. The browser sees a single origin so no CORS
headers are needed and `PCE_ALLOWED_ORIGINS` must be left empty.

```
browser → http://localhost:3000/          → web/dist (React SPA)
browser → http://localhost:3000/v1/*      → Nginx → context-api:8080
```

### Separate subdomain / CDN (opt-in CORS)

If the frontend is hosted on a different origin set `PCE_ALLOWED_ORIGINS` on
the context-api container. The Go CORS middleware will then emit
`Access-Control-Allow-Origin` only for listed origins and answer `OPTIONS`
preflight requests with 204.

```
PCE_ALLOWED_ORIGINS=https://pce.yourdomain.com,https://pce-staging.yourdomain.com
```

A wildcard is never emitted. Only explicitly listed origins receive CORS headers.
