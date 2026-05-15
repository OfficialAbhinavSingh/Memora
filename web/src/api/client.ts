const BASE = import.meta.env.VITE_API_BASE ?? '';

export const API_BASE = BASE || 'same-origin / Vite proxy';

export type ReconstructSignal = {
  incident_id: string;
  ts: string;
  tenant_id: string;
  environment: string;
  service_name?: string;
  canonical_service_id?: string;
  trigger: string;
};

export type ContextEvent = {
  event_id: string;
  ts: string;
  kind: string;
  tenant_id: string;
  environment: string;
  service_name?: string;
  canonical_service_id?: string;
  incident_id?: string;
  trace_id?: string;
  entities?: string[];
  attributes?: Record<string, unknown>;
  raw_ref?: string;
  provenance?: Record<string, unknown>;
};

export type CausalEdge = {
  cause_id: string;
  effect_id: string;
  evidence: string[];
  confidence: number;
};

export type IncidentMatch = {
  past_incident_id: string;
  similarity: number;
  rationale: string;
};

export type Remediation = {
  action: string;
  target: string;
  historical_outcome: string;
  confidence: number;
};

export type ContextResponse = {
  related_events: ContextEvent[];
  causal_chain: CausalEdge[];
  similar_past_incidents: IncidentMatch[];
  suggested_remediations: Remediation[];
  confidence: number;
  explain: string;
};

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => apiFetch<{ status: string }>('/v1/health'),
  readiness: () => apiFetch<{ status: string }>('/v1/readiness'),
  metrics: () => apiFetch<string>('/v1/metrics'),

  reconstruct: (signal: ReconstructSignal, mode: 'fast' | 'deep' = 'fast') =>
    apiFetch<ContextResponse>('/v1/context/reconstruct', {
      method: 'POST',
      body: JSON.stringify({ signal, mode }),
    }),

  getMemory: (id: string) => apiFetch(`/v1/incidents/${id}/memory`),

  submitFeedback: (payload: {
    incident_id: string;
    tenant_id: string;
    environment: string;
    action: string;
    target: string;
    outcome: 'worked' | 'failed' | 'unsure' | 'resolved' | 'success';
    observed_at: string;
    version?: string;
    service_name?: string;
    canonical_service_id?: string;
  }) =>
    apiFetch('/v1/feedback/remediation-outcome', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  registerAlias: (payload: {
    tenant_id: string;
    environment: string;
    from: string;
    to: string;
    observed_at?: string;
    confidence?: number;
  }) =>
    apiFetch('/v1/topology/alias', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
