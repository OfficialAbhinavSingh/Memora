import { DEMO_INCIDENTS_HISTORY } from '../data/mockData';
import { SeverityBadge, StatusBadge, PageHeader } from '../components/ui';
import { useNavigate } from 'react-router-dom';

export default function IncidentHistory() {
  const nav = useNavigate();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader title="Incident History" subtitle={`${DEMO_INCIDENTS_HISTORY.length} incidents · all environments`} />
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        <div className="panel" style={{ overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr><th>Incident ID</th><th>Service</th><th>Severity</th><th>Status</th><th>Started</th><th>Duration</th><th>Summary</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {DEMO_INCIDENTS_HISTORY.map(inc => (
                <tr key={inc.id}>
                  <td><span className="mono text-xs" style={{ color: 'var(--accent)', fontWeight: 600 }}>{inc.id}</span></td>
                  <td><span className="mono text-xs">{inc.service}</span></td>
                  <td><SeverityBadge sev={inc.severity} /></td>
                  <td><StatusBadge status={inc.status} /></td>
                  <td><span className="mono text-xs text-muted">{inc.started}</span></td>
                  <td><span className="mono text-xs text-muted">{inc.duration}</span></td>
                  <td style={{ fontSize: 12 }}>{inc.summary}</td>
                  <td>
                    <button className="btn-ghost btn-sm" onClick={() => nav('/')}>Reconstruct</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
