# PCE Frontend

React + TypeScript frontend for the **Persistent Context Engine** — an operational memory platform for SREs and platform engineers.

## Stack
- **Vite** + **React** + **TypeScript**
- **react-router-dom** for routing
- **lucide-react** for icons
- Pure CSS design system (no Tailwind)

## Dev
```bash
cd web
npm install
npm run dev        # → http://localhost:5173
```

The dev server proxies `/v1/*` requests to `http://localhost:8080` (the PCE Go backend).

## Build
```bash
npm run build      # → web/dist/
```

## Pages

| Route | Page |
|-------|------|
| `/` | Incident Workspace (primary) |
| `/history` | Incident History |
| `/timeline` | Investigation Timeline |
| `/causal` | Causal Chain View |
| `/similar` | Similar Incidents |
| `/remediations` | Remediation Panel |
| `/topology` | Topology Alias Management |
| `/health` | System Health |

## Backend Integration

The API client lives in `src/api/client.ts`. All endpoints map to the real PCE backend:

| UI action | Endpoint |
|-----------|----------|
| Health check | `GET /v1/health` |
| Readiness check | `GET /v1/readiness` |
| Metrics | `GET /v1/metrics` |
| Reconstruct context | `POST /v1/context/reconstruct` |
| Get incident memory | `GET /v1/incidents/{id}/memory` |
| Submit feedback | `POST /v1/feedback/remediation-outcome` |
| Register alias | `POST /v1/topology/alias` |

When the backend is unavailable, the app uses seeded mock data in `src/data/mockData.ts` that pre-loads the **billing-svc incident demo scenario**.

## Demo Scenario

Pre-loaded incident `INC-2024-0847`:
- `payments-svc` renamed to `billing-svc`
- Deploy `v2.4.1` deployed at 14:22 UTC
- Connection pool config reduced: `pool_max: 200 → 50`
- P99 latency spike: `120ms → 2100ms`
- `checkout-api` timeout cascade, error rate `1.2% → 12.3%`
- System detected topology alias via `svc-00441`
- Matched `INC-2023-1204` at 93% similarity
- Rollback to `v2.3.9` suggested at 87% confidence
