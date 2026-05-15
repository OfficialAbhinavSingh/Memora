import { useState } from 'react';
import { DEMO_SIMILAR, DEMO_INCIDENT } from '../data/mockData';
import { ConfBar, PageHeader } from '../components/ui';

const SIGNALS = ['pool_max config reduction','deploy-triggered','connection pool exhaustion','latency P99 spike','upstream cascade','rollback-resolved'];

export default function SimilarIncidents() {
  const [selected, setSelected] = useState(0);
  const sel = DEMO_SIMILAR[selected];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="Similar Incidents"
        subtitle={`Matched against ${DEMO_INCIDENT.id} · billing-svc · deploy-related latency spike`}
      />
      <div style={{ padding: '6px 20px 8px', borderBottom: '1px solid var(--border)' }}>
        <span className="text-xs text-muted">3 historical incidents found · pattern: deploy config change → pool exhaustion → cascade</span>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
        {/* Left list */}
        <div style={{ width: '38%', borderRight: '1px solid var(--border)', overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {DEMO_SIMILAR.map((s, i) => (
            <div
              key={s.id}
              onClick={() => setSelected(i)}
              className="panel"
              style={{
                padding: 12, cursor: 'pointer',
                borderLeft: `3px solid ${i === selected ? 'var(--accent)' : 'transparent'}`,
                background: i === selected ? 'var(--surface-high)' : 'var(--surface)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span className="mono text-xs" style={{ fontWeight: 700, color: 'var(--text-heading)' }}>{s.id}</span>
                <span className={`badge ${s.score >= 80 ? 'badge-green' : s.score >= 60 ? 'badge-amber' : 'badge-gray'}`}>{s.score}% match</span>
              </div>
              <div className="mono text-xs text-muted" style={{ marginBottom: 4 }}>{s.service} · {s.date}</div>
              <div style={{ fontSize: 11, color: 'var(--text-body)', marginBottom: 4 }}>{s.rationale}</div>
              <div className="text-xs" style={{ color: 'var(--green)' }}>✓ {s.resolution}</div>
              <div className="text-xs text-muted">Duration: {s.duration}</div>
            </div>
          ))}
        </div>

        {/* Right comparison */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {sel.comparison ? (
            <>
              <div style={{ fontWeight: 600, color: 'var(--text-heading)', fontSize: 14, marginBottom: 14 }}>
                {sel.id} vs {DEMO_INCIDENT.id}
              </div>
              <table className="data-table" style={{ marginBottom: 16 }}>
                <thead>
                  <tr><th>Attribute</th><th>Past ({sel.id})</th><th>Current ({DEMO_INCIDENT.id})</th></tr>
                </thead>
                <tbody>
                  <tr><td className="text-muted">Service</td><td className="mono text-xs">payments-svc</td><td className="mono text-xs">billing-svc (renamed)</td></tr>
                  <tr><td className="text-muted">Trigger</td><td className="mono text-xs">{sel.comparison.trigger}</td><td className="mono text-xs">Deploy v2.4.1</td></tr>
                  <tr><td className="text-muted">Config change</td><td className="mono text-xs">{sel.comparison.configChange}</td><td className="mono text-xs">pool_max: 200→50</td></tr>
                  <tr><td className="text-muted">Latency spike</td><td className="mono text-xs">{sel.comparison.latencySpike}</td><td className="mono text-xs">P99: 120ms→2100ms</td></tr>
                  <tr><td className="text-muted">Cascade to</td><td className="mono text-xs">{sel.comparison.cascadeTo}</td><td className="mono text-xs">checkout-api</td></tr>
                  <tr><td className="text-muted">Time to detect</td><td className="mono text-xs">{sel.comparison.timeToDetect}</td><td className="mono text-xs">2m 27s</td></tr>
                  <tr><td className="text-muted">Resolution</td><td className="mono text-xs">{sel.comparison.resolution}</td><td className="mono text-xs">Suggested: Rollback v2.3.9</td></tr>
                  <tr><td className="text-muted">Outcome</td><td style={{ color: 'var(--green)' }} className="mono text-xs">{sel.comparison.outcome}</td><td className="text-xs badge badge-amber">Pending</td></tr>
                </tbody>
              </table>

              <div className="section-label" style={{ marginBottom: 8 }}>Rationale</div>
              <div style={{ fontSize: 12, color: 'var(--text-body)', lineHeight: 1.7, marginBottom: 14, padding: 12, background: 'var(--surface)', borderRadius: 'var(--radius)' }}>
                The causal pattern is nearly identical: a deploy with a pool_max configuration reduction caused connection pool exhaustion under existing load. The service rename (payments-svc → billing-svc) was correctly resolved via topology alias matching. The cascade path changed (api-gateway → checkout-api) but the root cause and resolution are structurally identical.
              </div>

              <div className="section-label" style={{ marginBottom: 8 }}>Matching Signals</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
                {SIGNALS.map(s => <span key={s} className="badge badge-blue">{s}</span>)}
              </div>

              <div className="panel" style={{ padding: 14, borderColor: 'rgba(34,197,94,0.3)' }}>
                <div className="section-label" style={{ color: 'var(--green)', marginBottom: 8 }}>Remediation Transferred from {sel.id}</div>
                <div style={{ fontSize: 12, marginBottom: 8, lineHeight: 1.6 }}>Rollback resolved {sel.id} in 8 minutes with zero recurrence in 90 days.</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span className="text-xs text-muted">Confidence transferred:</span>
                  <div style={{ width: 100 }}><ConfBar value={87} /></div>
                </div>
                <button className="btn-primary">Apply Remediation</button>
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', padding: 20, fontSize: 12 }}>Select an incident to compare.</div>
          )}
        </div>
      </div>
    </div>
  );
}
