import { DEMO_HEALTH } from '../data/mockData';
import { PageHeader } from '../components/ui';

export default function SystemHealth() {
  const { health, readiness, metrics, recentCalls } = DEMO_HEALTH;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="System Health"
        subtitle="Internal status · PCE API v1"
        right={
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--green)', display: 'inline-block', boxShadow: '0 0 4px var(--green)' }} />
            <span className="text-xs" style={{ color: 'var(--green)' }}>Live · checked 2s ago</span>
          </div>
        }
      />
      <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Health + Readiness cards */}
        <div style={{ display: 'flex', gap: 12 }}>
          {[
            { label: 'Health · GET /v1/health', status: health.status, latency: health.latency, extras: [`Uptime: ${health.uptime}% (30d)`] },
            { label: 'Readiness · GET /v1/readiness', status: readiness.status, latency: readiness.latency, extras: Object.entries(readiness.deps).map(([k, v]) => `${v ? '✓' : '✗'} ${k}`) },
          ].map(card => (
            <div key={card.label} className="panel" style={{ flex: 1, padding: 14 }}>
              <div className="section-label" style={{ marginBottom: 10 }}>{card.label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--green)' }}>{card.status}</span>
              </div>
              <div className="text-xs text-muted mono" style={{ marginBottom: 6 }}>Response: {card.latency}ms</div>
              {card.extras.map(e => <div key={e} className="text-xs mono" style={{ color: 'var(--text-body)', marginBottom: 2 }}>{e}</div>)}
            </div>
          ))}
        </div>

        {/* Metrics grid */}
        <div className="panel" style={{ padding: 14 }}>
          <div className="section-label" style={{ marginBottom: 12 }}>Metrics · GET /v1/metrics</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
            {Object.entries(metrics).map(([key, m]) => (
              <div key={key} style={{ padding: '10px 12px', background: 'var(--surface-low)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <div className="label-caps" style={{ marginBottom: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{key.replace(/_/g,' ')}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 2 }}>{String(m.value)}</div>
                <div className="text-xs text-muted">{m.delta}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent API calls */}
        <div className="panel" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid var(--border)' }}>
            <span className="section-label">Recent API Calls (last 10 minutes)</span>
          </div>
          <table className="data-table">
            <thead>
              <tr><th>Timestamp</th><th>Endpoint</th><th>Method</th><th>Status</th><th>Latency</th></tr>
            </thead>
            <tbody>
              {recentCalls.map((c, i) => (
                <tr key={i}>
                  <td><span className="mono text-xs text-muted">{c.ts} UTC</span></td>
                  <td><span className="mono text-xs">{c.endpoint}</span></td>
                  <td><span className={`badge ${c.method === 'POST' ? 'badge-blue' : 'badge-gray'}`}>{c.method}</span></td>
                  <td><span className="mono text-xs" style={{ color: c.status < 300 ? 'var(--green)' : 'var(--red)' }}>{c.status}</span></td>
                  <td><span className="mono text-xs text-muted">{c.latency}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
