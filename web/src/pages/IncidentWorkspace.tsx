import { useState } from 'react';
import { Search, RefreshCw } from 'lucide-react';
import {
  DEMO_INCIDENT, DEMO_EVENTS, DEMO_CAUSAL_CHAIN,
  DEMO_SIMILAR, DEMO_REMEDIATIONS
} from '../data/mockData';
import { ConfBar, EventTypeBadge, EventBorderClass, PageHeader } from '../components/ui';

export default function IncidentWorkspace() {
  const [query, setQuery] = useState('INC-2024-0847');
  const [feedback, setFeedback] = useState<Record<number, string>>({});

  const inc = DEMO_INCIDENT;
  const confTier = inc.confidence >= 80 ? 'high' : inc.confidence >= 50 ? 'mid' : 'low';

  return (
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <PageHeader
          title="Incident Workspace"
          subtitle={`${inc.id} · ${inc.service} · ${inc.severity}`}
          right={
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ position: 'relative' }}>
                <Search size={12} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search incident ID or service…"
                  style={{ padding: '5px 10px 5px 28px', width: 260 }}
                />
              </div>
              <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <RefreshCw size={12} /> Reconstruct Context
              </button>
            </div>
          }
        />

        <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Context Summary */}
          <div className="panel" style={{ padding: 14 }}>
            <div className="section-label">Context Reconstruction</div>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>{inc.title}</div>
                <div className="text-xs mono text-muted">
                  Started {inc.startedAgo} · {inc.renamedFrom} → {inc.service} (renamed) · deploy @ {inc.deployTime}
                </div>
              </div>
              <div style={{ flexShrink: 0, width: 180 }}>
                <div className="text-xs text-muted" style={{ marginBottom: 4 }}>Confidence</div>
                <ConfBar value={inc.confidence} />
              </div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7, padding: '10px 12px', background: 'var(--surface-low)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--accent)' }}>
              {inc.explain}
            </div>
          </div>

          {/* Related Events */}
          <div className="panel" style={{ overflow: 'hidden' }}>
            <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid var(--border)' }}>
              <span className="section-label">Related Events ({DEMO_EVENTS.length})</span>
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
                {DEMO_EVENTS.map(ev => (
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

      {/* Right rail */}
      <div style={{ width: 300, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflow: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Causal Chain */}
          <div>
            <div className="section-label">Causal Chain</div>
            {DEMO_CAUSAL_CHAIN.map((node, i) => (
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

          {/* Similar Incidents */}
          <div>
            <div className="section-label">Similar Incidents</div>
            {DEMO_SIMILAR.slice(0, 2).map(s => (
              <div key={s.id} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono text-xs" style={{ color: 'var(--text-heading)', fontWeight: 600 }}>{s.id}</span>
                  <span className={`badge ${s.score >= 80 ? 'badge-green' : s.score >= 60 ? 'badge-amber' : 'badge-gray'}`}>{s.score}%</span>
                </div>
                <div className="text-xs text-muted">{s.rationale}</div>
                <div className="text-xs" style={{ color: 'var(--green)', marginTop: 4 }}>✓ {s.resolution}</div>
              </div>
            ))}
          </div>

          <hr className="divider" />

          {/* Remediations */}
          <div>
            <div className="section-label">Remediations</div>
            {DEMO_REMEDIATIONS.slice(0, 2).map((r, i) => (
              <div key={r.rank} className="panel" style={{ padding: '8px 10px', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, alignItems: 'flex-start', gap: 6 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)', flex: 1 }}>#{r.rank} {r.title}</div>
                  <span className={`badge badge-${r.labelColor}`}>{r.label}</span>
                </div>
                <ConfBar value={r.confidence} />
                <div className="text-xs text-muted" style={{ margin: '6px 0 6px' }}>{r.history}</div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(['worked', 'failed', 'unsure'] as const).map(o => (
                    <button
                      key={o}
                      className="btn-ghost btn-sm"
                      style={feedback[i] === o ? { background: 'var(--accent-dim)', borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}
                      onClick={() => setFeedback(f => ({ ...f, [i]: o }))}
                    >
                      {o === 'worked' ? '✓ Worked' : o === 'failed' ? '✗ Failed' : '? Unsure'}
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
