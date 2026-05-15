# PCE Frontend

React + TypeScript frontend for the Persistent Context Engine.

## Stack

- Vite + React + TypeScript
- react-router-dom for routing
- lucide-react for icons
- Pure CSS design system

## Dev

```bash
cd web
npm install
npm run dev
```

The dev server runs at `http://localhost:5173`.

## API URL

Create `web/.env` from `web/.env.example`.

For normal local development, leave it blank:

```bash
VITE_API_BASE=
```

That uses the Vite proxy in `vite.config.ts`, sending `/v1/*` to `http://localhost:8080` and avoiding browser CORS issues.

If the API is hosted elsewhere, set:

```bash
VITE_API_BASE=http://localhost:8080
```

## Build

```bash
npm run lint
npm run build
```

## Pages

| Route | Page |
| --- | --- |
| `/` | Incident Workspace |
| `/history` | Incident History |
| `/timeline` | Investigation Timeline |
| `/causal` | Causal Chain View |
| `/similar` | Similar Incidents |
| `/remediations` | Remediation Panel |
| `/topology` | Topology Alias Management |
| `/health` | System Health |

## Backend Integration

The API client lives in `src/api/client.ts`.

| UI action | Endpoint |
| --- | --- |
| Health check | `GET /v1/health` |
| Readiness check | `GET /v1/readiness` |
| Metrics | `GET /v1/metrics` |
| Reconstruct context | `POST /v1/context/reconstruct` |
| Get incident memory | `GET /v1/incidents/{id}/memory` |
| Submit feedback | `POST /v1/feedback/remediation-outcome` |
| Register alias | `POST /v1/topology/alias` |

The Incident Workspace does not show mock data as live data. If the backend is unavailable, it shows an empty/API-unavailable state until telemetry is ingested and reconstruction succeeds.

## Demo Fixtures

Fixture data still exists in `src/data/mockData.ts` for secondary static pages and future demo-mode work. It is not used as the live Incident Workspace response.
