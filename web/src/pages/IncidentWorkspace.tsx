import { useState } from 'react';
import { Search, RefreshCw } from 'lucide-react';
import { api, type ContextResponse, type ContextEvent } from '../api/client';
import {
  DEMO_INCIDENT, DEMO_EVENTS, DEMO_CAUSAL_CHAIN,
  DEMO_SIMILAR, DEMO_REMEDIATIONS
} from '../data/mockData';
import { ConfBar, EventTypeBadge, EventBorderClass, PageHeader } from '../components/ui';

const DEFAULT_SIGNAL = {
  tenant_id: DEMO_INCIDENT.tenantId,
  environment: 'prod',
  service_name: DEMO_INCIDENT.service,
  trigger: 'alert:checkout-api/error-rate>5%',
};

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
  const pieces = [
    event.event_id ? `id:${event.event_id.slice(0, 8)}` : '',
    event.trace_id ? `trace:${event.trace_id}` : '',
    event.canonical_service_id ?? '',
  ].filter(Boolean);
  return pieces.join(' / ');
}

export default function IncidentWorkspace() {
  const [query, setQuery] = useState('INC-2024-0847');
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [context, setContext] = useState<ContextResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState('');

  const inc = DEMO_INCIDENT;
  const confidence = context ? percent(context.confidence) : inc.confidence;
  const relatedEvents = context?.related_events ?? [];
  const causalChain = context?.causal_chain ?? [];
  const similarIncidents = context?.similar_past_incidents ?? [];
  const remediations = context?.suggested_remediations ?? [];

  async function reconstruct() {
    setLoading(true);
    setApiError('');
    try {
      const next = await api.reconstruct({
        incident_id: query || inc.id,
        ts: new Date().toISOString(),
        ...DEFAULT_SIGNAL,
      });
      setContext(next);
    } catch (err) {
      setContext(null);
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
        incident_id: query || inc.id,
        tenant_id: DEFAULT_SIGNAL.tenant_id,
        environment: DEFAULT_SIGNAL.environment,
        action: remediation.action,
        target: remediation.target,
        outcome,
        observed_at: new Date().toISOString(),
        service_name: DEFAULT_SIGNAL.service_name,
      });
    } catch {
      // Keep the local acknowledgement. The API may be offline in demo mode.
    }
  }

  return (
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <PageHeader
          title="Incident Workspace"
          subtitle={`${query || inc.id} / ${inc.service} / ${inc.severity}`}
          right={
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ position: 'relative' }}>
                <Search size={12} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search incident ID or service"
                  style={{ padding: '5px 10px 5px 28px', width: 260 }}
                />
              </div>
              <button
                className="btn-primary"
                onClick={reconstruct}
                disabled={loading}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <RefreshCw size={12} /> {loading ? 'Reconstructing' : 'Reconstruct Context'}
              </button>
            </div>
          }
        />

        <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="panel" style={{ padding: 14 }}>
            <div className="section-label">Context Reconstruction</div>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>{inc.title}</div>
                <div className="text-xs mono text-muted">
                  {context ? 'Live API context' : 'Demo fallback context'} / {inc.renamedFrom} {'->'} {inc.service} / deploy @ {inc.deployTime}
                </div>
              </div>
              <div style={{ flexShrink: 0, width: 180 }}>
                <div className="text-xs text-muted" style={{ marginBottom: 4 }}>Confidence</div>
                <ConfBar value={confidence} />
              </div>
            </div>
            {apiError && (
              <div style={{ fontSize: 12, color: 'var(--amber)', marginBottom: 8 }}>
                API unavailable, showing demo memory: {apiError}
              </div>
            )}
            <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7, padding: '10px 12px', background: 'var(--surface-low)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--accent)' }}>
              {context?.explain ?? inc.explain}
            </div>
          </div>

          <div className="panel" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid var(--border)' }}>
              <span className="section-label">Related Events ({context ? relatedEvents.length : DEMO_EVENTS.length})</span>
            </div>
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
                {context ? relatedEvents.map(ev => (
                  <tr key={ev.event_id} className={EventBorderClass(ev.kind)}>
                    <td><EventTypeBadge kind={ev.kind} /></td>
                    <td><span className="mono text-xs">{new Date(ev.ts).toLocaleTimeString()}</span></td>
                    <td><span className="mono text-xs">{ev.service_name ?? ev.canonical_service_id ?? '-'}</span></td>
                    <td style={{ maxWidth: 380, fontSize: 12 }}>{eventDescription(ev)}</td>
                    <td><span className="mono text-xs text-muted">{eventMeta(ev)}</span></td>
                  </tr>
                )) : DEMO_EVENTS.map(ev => (
                  <tr key={ev.id} className={EventBorderClass(ev.kind)} style={ev.critical ? { background: 'rgba(239,68,68,0.04)' } : undefined}>
                    <td><EventTypeBadge kind={ev.kind} /></td>
                    <td><span className="mono text-xs">{ev.ts} UTC</span></td>
                    <td><span className="mono text-xs">{ev.service}</span></td>
                    <td style={{ maxWidth: 380, fontSize: 12 }}>{ev.desc}</td>
                    <td><span className="mono text-xs text-muted">{ev.meta}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div style={{ width: 300, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflow: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <div className="section-label">Causal Chain</div>
            {context ? causalChain.map((edge, i) => (
              <div key={`${edge.cause_id}-${edge.effect_id}`} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div className="text-xs text-muted" style={{ marginBottom: 3 }}>EDGE {i + 1}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>
                  {edge.cause_id.slice(0, 8)} {'->'} {edge.effect_id.slice(0, 8)}
                </div>
                <div className="text-xs text-muted" style={{ marginBottom: 6 }}>{edge.evidence.join(', ')}</div>
                <ConfBar value={percent(edge.confidence)} />
              </div>
            )) : DEMO_CAUSAL_CHAIN.map((node, i) => (
              <div key={node.id}>
                {i > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0 4px 10px' }}>
                    <div style={{ width: 1, height: 14, background: 'var(--border)', marginLeft: 5 }} />
                    <span className="text-xs text-muted">{node.edgeLabel} <span className="mono" style={{ color: 'var(--accent)' }}>{node.edgeConf}%</span></span>
                  </div>
                )}
                <div className="panel" style={{ padding: '8px 10px' }}>
                  <div className="text-xs text-muted" style={{ marginBottom: 3 }}>{node.label}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>{node.event}</div>
                  <ConfBar value={node.confidence} />
                </div>
              </div>
            ))}
          </div>

          <hr className="divider" />

          <div>
            <div className="section-label">Similar Incidents</div>
            {context ? similarIncidents.slice(0, 2).map(s => (
              <div key={s.past_incident_id} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono text-xs" style={{ color: 'var(--text-heading)', fontWeight: 600 }}>{s.past_incident_id}</span>
                  <span className={`badge ${percent(s.similarity) >= 80 ? 'badge-green' : percent(s.similarity) >= 60 ? 'badge-amber' : 'badge-gray'}`}>{percent(s.similarity)}%</span>
                </div>
                <div className="text-xs text-muted">{s.rationale}</div>
              </div>
            )) : DEMO_SIMILAR.slice(0, 2).map(s => (
              <div key={s.id} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono text-xs" style={{ color: 'var(--text-heading)', fontWeight: 600 }}>{s.id}</span>
                  <span className={`badge ${s.score >= 80 ? 'badge-green' : s.score >= 60 ? 'badge-amber' : 'badge-gray'}`}>{s.score}%</span>
                </div>
                <div className="text-xs text-muted">{s.rationale}</div>
                <div className="text-xs" style={{ color: 'var(--green)', marginTop: 4 }}>{s.resolution}</div>
              </div>
            ))}
          </div>

          <hr className="divider" />

          <div>
            <div className="section-label">Remediations</div>
            {context ? remediations.slice(0, 2).map((r, i) => (
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
            )) : DEMO_REMEDIATIONS.slice(0, 2).map((r, i) => (
              <div key={r.rank} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, alignItems: 'flex-start', gap: 6 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)', flex: 1 }}>#{r.rank} {r.title}</div>
                  <span className={`badge badge-${r.labelColor}`}>{r.label}</span>
                </div>
                <ConfBar value={r.confidence} />
                <div className="text-xs text-muted" style={{ margin: '6px 0 6px' }}>{r.history}</div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['worked', 'failed', 'unsure'] as const).map(o => (
                    <button key={o} className="btn-ghost btn-sm" onClick={() => setFeedback(f => ({ ...f, [i]: o }))}>
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
