<p align="center">
  <img src="https://img.shields.io/badge/Anvil-P--02-blueviolet?style=for-the-badge" alt="Anvil P-02" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Go-1.21+-00ADD8?style=for-the-badge&logo=go&logoColor=white" alt="Go 1.21+" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 18" />
  <img src="https://img.shields.io/badge/stdlib--only-no_deps-success?style=for-the-badge" alt="stdlib only" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License" />
</p>

<h1 align="center">Memora</h1>
<h3 align="center">Persistent Context Engine for Autonomous SRE</h3>

<p align="center">
  <em>An operational memory substrate that turns telemetry into long-lived incident reasoning &mdash; not dashboards, not search results.</em>
</p>

<p align="center">
  <a href="#-benchmark-results">Benchmark</a> &nbsp;&bull;&nbsp;
  <a href="#-architecture">Architecture</a> &nbsp;&bull;&nbsp;
  <a href="#-quick-start">Quick Start</a> &nbsp;&bull;&nbsp;
  <a href="#-api-reference">API</a> &nbsp;&bull;&nbsp;
  <a href="#-project-structure">Structure</a> &nbsp;&bull;&nbsp;
  <a href="docs/p02-writeup.md">Technical Writeup</a>
</p>

---

## What is Memora?

Memora is a **persistent context engine** built for the [Anvil P-02](https://github.com/Sauhard74/Anvil-P-E/tree/main/bench-p02-context) competition track. It solves the core challenge of autonomous SRE: **recognizing recurring incident patterns across topology drift, service renames, and behavioral morphing** — then recommending historically successful remediations.

Unlike embedding-based retrieval or keyword-matching systems, Memora forms structured **operational profiles** from ordered behavioral evidence and explains every match through lineage, temporal, causal, and remediation proof.

### Key Capabilities

| Capability | Description |
|:---|:---|
| **Topology Drift Resolution** | Chained rename propagation via alias graph — `payments-svc → billing-svc → ledger-v2` all resolve to one canonical identity |
| **Behavioral Shape Matching** | Incidents matched by deploy → anomaly → failure → remediation patterns, not string similarity |
| **Confidence-Adaptive Ranking** | Dynamically allocates return slots based on lineage confidence — aggressive precision when certain, conservative recall when uncertain |
| **Remediation Transfer** | Suggests historically successful actions with age-decay, success/failure reinforcement, and target remapping |
| **Full Reasoning Audit** | Every match includes lineage proof, shape scores, temporal comparison, confidence contributors — fully inspectable |

---

## 📊 Benchmark Results

> **Anvil P-02 Benchmark** — Corrected ground-truth alignment, 29 seeds, 5 difficulty tiers

<table>
<tr>
<td>

### Aggregate Metrics

| Metric | Score |
|:---|:---:|
| **recall@5** | **1.000** |
| **precision@5** | **0.818** |
| **remediation_acc** | **1.000** |
| **latency_p95** | **78 ms** |
| **Weighted Automated** | **0.769 / 0.80** |

</td>
<td>

### Per-Tier Breakdown

| Tier | Svcs | Days | Seeds | R@5 | P@5 | Score |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| Quick | 6 | 2 | 2 | 1.000 | 0.580 | 0.737 |
| Standard | 12 | 7 | 5 | 1.000 | 0.780 | 0.767 |
| Competition | 20 | 14 | 5 | 1.000 | 0.904 | 0.786 |
| Stress | 30 | 21 | 7 | 1.000 | 0.869 | 0.780 |
| Adversarial | 20 | 14 | 10 | 1.000 | 0.818 | 0.773 |

</td>
</tr>
</table>

**Notable per-seed peaks:** Seeds 404, 9999, 99999, 173205080 achieve **precision@5 = 1.000** (every returned incident is correct family).

> **Latency budget:** Fast mode requires < 2000 ms p95. Memora achieves **78 ms worst-case** — **25x headroom**.

<details>
<summary><b>Scoring weights (official Anvil P-02)</b></summary>

| Axis | Weight | Memora Score | Contribution |
|:---|:---:|:---:|:---:|
| recall@5 | 0.30 | 1.000 | 0.300 |
| precision@5_mean | 0.15 | 0.818 | 0.123 |
| remediation_acc | 0.20 | 1.000 | 0.200 |
| latency_p95 vs budget | 0.15 | 1.000 | 0.150 |
| manual_context | 0.10 | *(panel)* | — |
| manual_explain | 0.10 | *(panel)* | — |
| **Total Automated** | **0.80** | | **0.769** |

</details>

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Memora Engine                            │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │  Ingest  │→ │  Normalize   │→ │   Alias Graph (Topology)  │  │
│  │  Events  │  │  & Index     │  │   Chained Rename BFS      │  │
│  └──────────┘  └──────────────┘  └───────────────────────────┘  │
│                       │                        │                 │
│                       ▼                        ▼                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Incident Profile Builder                     │   │
│  │  deploys · anomaly metrics · failure logs · traces        │   │
│  │  remediations · behavioral signature · shape key          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            Context Reconstruction Pipeline                │   │
│  │                                                           │   │
│  │  1. Related Event Ranking (lineage + temporal + entity)   │   │
│  │  2. Causal Chain Synthesis (deploy→spike→failure edges)   │   │
│  │  3. Similar Incident Matching (shape + lineage + trigger) │   │
│  │  4. Confidence-Adaptive Ranking (quality-gated recall)    │   │
│  │  5. Remediation Transfer (feedback + decay + remapping)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Context Output                         │   │
│  │  related_events · causal_chain · similar_past_incidents   │   │
│  │  suggested_remediations · confidence · explain · audit    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Production Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **API** | Go 1.21+ | Context API — ingest, reconstruct, feedback, topology |
| **Telemetry Store** | ClickHouse | High-throughput normalized event storage |
| **Control Plane** | PostgreSQL | Aliases, feedback, incident memories (JSONB) |
| **Graph Projection** | Neo4j | Mirrored relationship projection (write path) |
| **Streaming** | Kafka + Flink | Real-time event ingestion and enrichment |
| **Cache** | Redis | Hot-path alias and context caching |
| **Frontend** | React 18 + Vite | 9-route SPA — investigation workspace, causal chains, benchmark dashboard |
| **Benchmark Adapter** | Python (stdlib-only) | Zero-dependency scoring adapter for Anvil harness |
| **Observability** | OTEL Collector + Prometheus | Distributed tracing, metrics export |
| **Deployment** | Docker Compose / Helm / ArgoCD | Local dev → Kubernetes production |

---

## 🚀 Quick Start

### Benchmark Adapter (Competition Scoring)

The benchmark adapter is **stdlib-only Python** — no pip install, no Docker, no network:

```bash
# Worked example + regression suite
python bench/worked_example_check.py
python bench/regression_check.py

# Official Anvil P-02 harness (place bench-p02-context/ in repo root)
cd bench-p02-context
python self_check.py --adapter adapters.memora:Engine --quick

# Full multi-seed run
python run.py --adapter adapters.memora:Engine --mode fast \
  --seeds 9999 31415 27182 16180 11235 \
  --n-services 20 --days 14 --out report.json
```

### Custom L3-Style Benchmark

```bash
# 29 seeds across 5 tiers with corrected ground-truth alignment
python bench/custom_benchmark.py
```

### Go API (Local Development)

```bash
cd services/context-api
go test ./...
go run ./cmd/context-api    # starts on :8080
```

### Full Infrastructure Stack

```bash
docker compose up --build   # API + ClickHouse + Postgres + Neo4j + Web UI
```

### Frontend

```bash
cd web
npm install && npm run dev  # starts on :5173
```

---

## 📡 API Reference

Base URL: `http://localhost:8080`

| Method | Endpoint | Auth | Description |
|:---:|:---|:---:|:---|
| `POST` | `/v1/ingest/events` | 🔒 | Ingest normalized telemetry events |
| `POST` | `/v1/context/reconstruct` | 🔒 | Reconstruct incident context from signal |
| `GET` | `/v1/incidents/{id}/memory` | 🔒 | Retrieve stored incident memory |
| `POST` | `/v1/feedback/remediation-outcome` | 🔒 | Record remediation success/failure |
| `POST` | `/v1/topology/alias` | 🔒 | Register service rename/alias |
| `GET` | `/v1/health` | — | Liveness probe |
| `GET` | `/v1/readiness` | — | Store-aware readiness probe |
| `GET` | `/v1/metrics` | — | Prometheus-format metrics |

> Set `PCE_API_KEY` to require `Authorization: Bearer <key>` on protected endpoints.

<details>
<summary><b>Example: Reconstruct Context</b></summary>

```bash
curl -X POST http://localhost:8080/v1/context/reconstruct \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "INC-1001",
    "ts": "2026-05-01T12:00:00Z",
    "trigger": "alert:billing-svc/latency_p99_ms>3000",
    "service": "billing-svc"
  }'
```

**Response shape:**
```json
{
  "related_events": [...],
  "causal_chain": [...],
  "similar_past_incidents": [...],
  "suggested_remediations": [...],
  "confidence": 0.87,
  "explain": "..."
}
```

</details>

---

## 📂 Project Structure

```
Memora/
├── services/context-api/          # Go API server
│   ├── cmd/context-api/           #   entrypoint
│   ├── internal/api/              #   HTTP handlers, middleware, metrics
│   ├── internal/service/          #   core reconstruction engine
│   ├── internal/domain/           #   canonical data contracts
│   ├── internal/store/            #   storage interfaces
│   ├── internal/persistence/      #   ClickHouse, Postgres, Neo4j adapters
│   └── internal/memory/           #   in-memory stores (dev/test)
│
├── bench/                         # Benchmark adapter & tooling
│   ├── adapters/memora.py         #   stdlib-only scoring engine (~1300 LOC)
│   ├── custom_benchmark.py        #   L3-style 5-tier comprehensive eval
│   ├── worked_example_check.py    #   rename-continuity smoke test
│   ├── regression_check.py        #   11-test regression suite
│   └── run.ps1 / run.sh           #   full harness runner
│
├── web/                           # React 18 + Vite frontend
│   └── src/pages/                 #   9 routes (workspace, causal, similar, etc.)
│
├── contracts/openapi.yaml         # OpenAPI 3.0 specification
├── deploy/helm/pce/               # Kubernetes Helm chart
├── infra/                         # ClickHouse, Postgres, Neo4j, OTEL, Kafka configs
├── docker-compose.yaml            # Full local stack
├── docs/                          # Technical writeup, architecture, runbook
├── SUBMISSION.md                  # Judge-facing commands & reproducibility
└── PROJECT_CONTEXT.md             # Agent-readable project context
```

---

## 🔬 How It Works

### The Central Challenge: Topology Drift

The Anvil P-02 benchmark tests whether an engine can **recognize the same incident family when services are renamed**. A deploy → latency spike → rollback pattern on `payments-svc` must match the same pattern on `billing-svc` after a rename event.

Memora solves this with a **four-layer matching strategy:**

**1. Alias Graph Resolution**
```
payments-svc → billing-svc → ledger-v2    (all resolve to canonical: svc-04)
```
Chained rename propagation via BFS ensures any historical name resolves to the current canonical identity.

**2. Behavioral Shape Matching**
```
Shape key: deploy|<5m|anomaly|none|none|rollback|resolved
```
Each incident is profiled into a topology-independent behavioral signature. Two incidents with the same shape key are operationally equivalent regardless of service names.

**3. Confidence-Adaptive Ranking**
```
High confidence (lineage ≥ 1.0):  [correct, correct, correct, correct, other]  → P@5 = 0.80
Low confidence:                    [fam1, fam2, fam3, fam4, fam5]              → P@5 = 0.20
```
When the engine is confident about the correct family, it fills more slots from that family. When uncertain, it spreads across families to protect recall.

**4. Remediation Transfer**
```
Same lineage + same shape → suggest rollback (confidence: 0.85, based on 3 successes, 0 failures)
```
Historical remediation outcomes are transferred with age decay, success reinforcement, and target remapping through the alias graph.

---

## 🧪 Testing & Validation

| Test Suite | Command | What It Validates |
|:---|:---|:---|
| Worked Example | `python bench/worked_example_check.py` | Rename continuity, causal chain synthesis, remediation ranking |
| Regression Suite | `python bench/regression_check.py` | 11 invariants: schema, scoring, fallback, shape matching |
| Official Harness | `python self_check.py --adapter adapters.memora:Engine` | Multi-seed recall, precision, remediation, latency |
| Custom Benchmark | `python bench/custom_benchmark.py` | 5-tier L3-style eval: 6→50 services, 2→21 days, 29 seeds |
| Go Unit Tests | `cd services/context-api && go test ./...` | Chained renames, rollback history, feedback decay |

---

## 🐳 Docker

```bash
# Benchmark-only (no infrastructure needed)
docker build -t memora-p02 .
docker run --rm memora-p02

# Full stack (API + ClickHouse + Postgres + Neo4j + Web UI)
docker compose up --build
```

### Environment Variables

| Variable | Default | Description |
|:---|:---|:---|
| `CLICKHOUSE_DSN` | *(in-memory fallback)* | `http://clickhouse:8123` |
| `POSTGRES_DSN` | *(in-memory fallback)* | `postgres://pce:pce@postgres:5432/pce?sslmode=disable` |
| `NEO4J_URI` | *(disabled)* | `bolt://neo4j:7687` |
| `PCE_API_KEY` | *(disabled)* | Bearer token for protected endpoints |
| `PCE_ALLOWED_ORIGINS` | *(disabled)* | CORS origins for cross-domain frontend |

---

## 📋 Make Targets

| Command | Action |
|:---|:---|
| `make test` | Run Go unit tests |
| `make fmt` | Format Go source |
| `make vet` | Static analysis |
| `make run` | Start context API locally |
| `make bench` | Run benchmark smoke checks |
| `make web-lint` | Lint React frontend |
| `make web-build` | Production frontend build |
| `make web-docker` | Build Nginx + React Docker image |
| `make docker-up` | Start full infrastructure stack |
| `make docker-down` | Stop infrastructure stack |

---

## 📄 Submission Artifacts

| Artifact | Path | Description |
|:---|:---|:---|
| Scoring Adapter | `bench/adapters/memora.py` | stdlib-only benchmark engine |
| Custom Benchmark | `bench/custom_benchmark.py` | L3-style 5-tier evaluation suite |
| Technical Writeup | `docs/p02-writeup.md` | 3-page architecture & design writeup |
| Writeup PDF | `docs/p02-writeup.pdf` | PDF version for submission |
| Demo Script | `docs/demo-script.md` | 5-minute walkthrough |
| Benchmark Report | `web/public/benchmark-report.json` | Latest results (displayed by web UI) |
| OpenAPI Contract | `contracts/openapi.yaml` | Full API specification |
| Submission Guide | `SUBMISSION.md` | Judge commands & reproducibility |

---

## 🎯 Design Principles

- **Deterministic & Explainable** — No black-box retrieval. Every match includes full reasoning audit.
- **Behavior-First Matching** — Operational shape, not string overlap. Works across renames.
- **Zero External Dependencies** — Benchmark adapter uses only Python stdlib. No pip, no network.
- **Interface-Driven Storage** — ClickHouse, Postgres, Neo4j adapters behind clean interfaces; in-memory fallbacks for dev.
- **Production-Ready Scaffolding** — Helm, ArgoCD, Docker Compose, OTEL, Prometheus — ready for real deployment.

---

<p align="center">
  <b>Memora</b> — Built for <a href="https://github.com/Sauhard74/Anvil-P-E">Anvil P-02</a> &nbsp;·&nbsp; Persistent Context Engine for Autonomous SRE
</p>
