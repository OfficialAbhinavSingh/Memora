import { useState } from 'react';
import { Search, RefreshCw } from 'lucide-react';
import { API_BASE, api, type ContextResponse, type ContextEvent } from '../api/client';
import { ConfBar, EventTypeBadge, EventBorderClass, PageHeader } from '../components/ui';

function percent(value: number) {
  return Math.round(value <= 1 ? value * 100 : value);
}

function eventDescription(event: ContextEvent) {
  const attrs = event.attributes ?? {};
  if (event.kind === 'deploy') return `Deploy ${String(attrs.version ?? 'unknown version')}`;
  if (event.kind === 'metric') return `${String(attrs.name ?? 'metric')} = ${String(attrs.value ?? 'unknown')}`;
  if (event.kind === 'log') return String(attrs.msg ?? attrs.message ?? 'log event');
  if (event.kind === 'trace') return `Trace ${event.trace_id ?? ''} ${JSON.stringify(attrs.spans ?? attrs)}`;
  if (event.kind === 'topology') return `${String(attrs.change ?? 'topology')} ${String(attrs.from ?? '')} -> ${String(attrs.to ?? '')}`;
  if (event.kind === 'remediation') return `${String(attrs.action ?? 'remediation')} ${String(attrs.outcome ?? '')}`;
  return JSON.stringify(attrs);
}

function eventMeta(event: ContextEvent) {
  return [
    event.event_id ? `id:${event.event_id.slice(0, 8)}` : '',
    event.trace_id ? `trace:${event.trace_id}` : '',
    event.canonical_service_id ?? '',
  ].filter(Boolean).join(' / ');
}

function EmptyPanel({ title, body }: { title: string; body: string }) {
  return (
    <div className="panel" style={{ padding: '10px 12px', marginBottom: 8 }}>
      <div className="text-xs" style={{ color: 'var(--text-heading)', fontWeight: 600, marginBottom: 4 }}>{title}</div>
      <div className="text-xs text-muted">{body}</div>
    </div>
  );
}

export default function IncidentWorkspace() {
  const [incidentId, setIncidentId] = useState('INC-714');
  const [tenantId, setTenantId] = useState('default');
  const [environment, setEnvironment] = useState('prod');
  const [serviceName, setServiceName] = useState('billing-svc');
  const [trigger, setTrigger] = useState('alert:checkout-api/error-rate>5%');
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [context, setContext] = useState<ContextResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState('');

  const relatedEvents = context?.related_events ?? [];
  const causalChain = context?.causal_chain ?? [];
  const similarIncidents = context?.similar_past_incidents ?? [];
  const remediations = context?.suggested_remediations ?? [];

  async function reconstruct() {
    setLoading(true);
    setApiError('');
    setContext(null);
    try {
      const next = await api.reconstruct({
        incident_id: incidentId,
        ts: new Date().toISOString(),
        tenant_id: tenantId,
        environment,
        service_name: serviceName,
        trigger,
      });
      setContext(next);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Could not reach the Context API');
    } finally {
      setLoading(false);
    }
  }

  async function recordFeedback(index: number, outcome: 'worked' | 'failed' | 'unsure') {
    setFeedback(f => ({ ...f, [index]: outcome }));
    const remediation = remediations[index];
    if (!remediation) return;
    try {
      await api.submitFeedback({
        incident_id: incidentId,
        tenant_id: tenantId,
        environment,
        action: remediation.action,
        target: remediation.target,
        outcome,
        observed_at: new Date().toISOString(),
        service_name: serviceName,
      });
    } catch {
      setApiError('Feedback was not saved because the Context API is unavailable.');
    }
  }

  return (
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <PageHeader
          title="Incident Workspace"
          subtitle={`${incidentId} / ${serviceName} / API: ${API_BASE}`}
          right={
            <button
              className="btn-primary"
              onClick={reconstruct}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={12} /> {loading ? 'Reconstructing' : 'Reconstruct Context'}
            </button>
          }
        />

        <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="panel" style={{ padding: 14 }}>
            <div className="section-label">Incident Signal</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(120px, 1fr))', gap: 8, marginBottom: 12 }}>
              <label className="text-xs text-muted">Incident ID<input value={incidentId} onChange={e => setIncidentId(e.target.value)} style={{ width: '100%', marginTop: 4 }} /></label>
              <label className="text-xs text-muted">Tenant<input value={tenantId} onChange={e => setTenantId(e.target.value)} style={{ width: '100%', marginTop: 4 }} /></label>
              <label className="text-xs text-muted">Environment<input value={environment} onChange={e => setEnvironment(e.target.value)} style={{ width: '100%', marginTop: 4 }} /></label>
              <label className="text-xs text-muted">Service<input value={serviceName} onChange={e => setServiceName(e.target.value)} style={{ width: '100%', marginTop: 4 }} /></label>
              <label className="text-xs text-muted">Trigger<input value={trigger} onChange={e => setTrigger(e.target.value)} style={{ width: '100%', marginTop: 4 }} /></label>
            </div>
            {apiError && (
              <div style={{ fontSize: 12, color: 'var(--amber)', marginBottom: 8 }}>
                {apiError}
              </div>
            )}
            <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7, padding: '10px 12px', background: 'var(--surface-low)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--accent)' }}>
              {context?.explain ?? 'No reconstructed context yet. Start the Context API, ingest events, then run reconstruction.'}
            </div>
            {context && (
              <div style={{ marginTop: 10, maxWidth: 220 }}>
                <div className="text-xs text-muted" style={{ marginBottom: 4 }}>Confidence</div>
                <ConfBar value={percent(context.confidence)} />
              </div>
            )}
          </div>

          <div className="panel" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid var(--border)' }}>
              <span className="section-label">Related Events ({relatedEvents.length})</span>
            </div>
            {relatedEvents.length === 0 ? (
              <div style={{ padding: 24, color: 'var(--text-muted)', fontSize: 12 }}>
                <Search size={14} /> No live events returned yet.
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Timestamp</th>
                    <th>Service</th>
                    <th>Description</th>
                    <th>Meta</th>
                  </tr>
                </thead>
                <tbody>
                  {relatedEvents.map(ev => (
                    <tr key={ev.event_id} className={EventBorderClass(ev.kind)}>
                      <td><EventTypeBadge kind={ev.kind} /></td>
                      <td><span className="mono text-xs">{new Date(ev.ts).toLocaleTimeString()}</span></td>
                      <td><span className="mono text-xs">{ev.service_name ?? ev.canonical_service_id ?? '-'}</span></td>
                      <td style={{ maxWidth: 380, fontSize: 12 }}>{eventDescription(ev)}</td>
                      <td><span className="mono text-xs text-muted">{eventMeta(ev)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      <div style={{ width: 300, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflow: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <div className="section-label">Causal Chain</div>
            {causalChain.length === 0 ? <EmptyPanel title="No edges yet" body="Run reconstruction after ingesting telemetry." /> : causalChain.map((edge, i) => (
              <div key={`${edge.cause_id}-${edge.effect_id}`} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div className="text-xs text-muted" style={{ marginBottom: 3 }}>EDGE {i + 1}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>
                  {edge.cause_id.slice(0, 8)} {'->'} {edge.effect_id.slice(0, 8)}
                </div>
                <div className="text-xs text-muted" style={{ marginBottom: 6 }}>{edge.evidence.join(', ')}</div>
                <ConfBar value={percent(edge.confidence)} />
              </div>
            ))}
          </div>

          <hr className="divider" />

          <div>
            <div className="section-label">Similar Incidents</div>
            {similarIncidents.length === 0 ? <EmptyPanel title="No matches yet" body="Historical incident matches will appear here." /> : similarIncidents.slice(0, 2).map(s => (
              <div key={s.past_incident_id} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono text-xs" style={{ color: 'var(--text-heading)', fontWeight: 600 }}>{s.past_incident_id}</span>
                  <span className={`badge ${percent(s.similarity) >= 80 ? 'badge-green' : percent(s.similarity) >= 60 ? 'badge-amber' : 'badge-gray'}`}>{percent(s.similarity)}%</span>
                </div>
                <div className="text-xs text-muted">{s.rationale}</div>
              </div>
            ))}
          </div>

          <hr className="divider" />

          <div>
            <div className="section-label">Remediations</div>
            {remediations.length === 0 ? <EmptyPanel title="No suggestions yet" body="Suggested remediations depend on historical feedback." /> : remediations.slice(0, 2).map((r, i) => (
              <div key={`${r.action}-${r.target}`} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>#{i + 1} {r.action} {r.target}</div>
                <ConfBar value={percent(r.confidence)} />
                <div className="text-xs text-muted" style={{ margin: '6px 0 6px' }}>{r.historical_outcome}</div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['worked', 'failed', 'unsure'] as const).map(o => (
                    <button key={o} className="btn-ghost btn-sm" onClick={() => recordFeedback(i, o)}>
                      {feedback[i] === o ? `${o} saved` : o}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
