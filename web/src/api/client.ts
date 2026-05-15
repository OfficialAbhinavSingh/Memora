// API client — connects to real backend or falls back to mock data
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8080';

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => apiFetch<{ status: string }>('/v1/health'),
  readiness: () => apiFetch<{ status: string }>('/v1/readiness'),
  metrics: () => apiFetch<Record<string, unknown>>('/v1/metrics'),

  reconstruct: (incidentId: string, serviceHint?: string) =>
    apiFetch('/v1/context/reconstruct', {
      method: 'POST',
      body: JSON.stringify({ incident_id: incidentId, service_hint: serviceHint }),
    }),

  getMemory: (id: string) => apiFetch(`/v1/incidents/${id}/memory`),

  submitFeedback: (remediationId: string, outcome: 'worked' | 'failed' | 'unsure', incidentId: string) =>
    apiFetch('/v1/feedback/remediation-outcome', {
      method: 'POST',
      body: JSON.stringify({ remediation_id: remediationId, outcome, incident_id: incidentId }),
    }),

  registerAlias: (canonicalId: string, currentName: string, alias: string, env: string) =>
    apiFetch('/v1/topology/alias', {
      method: 'POST',
      body: JSON.stringify({ canonical_id: canonicalId, current_name: currentName, alias, environment: env }),
    }),
};
