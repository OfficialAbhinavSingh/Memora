import { useState } from 'react';
import { DEMO_ALIASES } from '../data/mockData';
import { PageHeader } from '../components/ui';

export default function TopologyAliases() {
  const [aliases, setAliases] = useState(DEMO_ALIASES);
  const [form, setForm] = useState({ canonicalId: '', current: '', alias: '', env: 'production' });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.canonicalId || !form.current || !form.alias) return;
    setAliases(a => [...a, { ...form, aliases: [form.alias], registered: new Date().toISOString().replace('T',' ').slice(0,16) + ' UTC', by: 'user' }]);
    setForm({ canonicalId: '', current: '', alias: '', env: 'production' });
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 3000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="Topology Alias Management"
        subtitle="Service lineage and rename tracking · POST /v1/topology/alias"
        right={<button className="btn-primary">+ Register Alias</button>}
      />
      <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Alias table */}
        <div className="panel" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid var(--border)' }}>
            <span className="section-label">Registered Aliases ({aliases.length})</span>
          </div>
          <table className="data-table">
            <thead>
              <tr><th>Canonical ID</th><th>Current Name</th><th>Aliases</th><th>Environment</th><th>Registered</th><th>By</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {aliases.map((a, i) => (
                <tr key={i}>
                  <td><span className="mono text-xs" style={{ color: 'var(--accent)' }}>{a.canonicalId}</span></td>
                  <td><span className="mono text-xs">{a.current}</span></td>
                  <td><span className="mono text-xs text-muted">{a.aliases.join(' → ')} → {a.current}</span></td>
                  <td><span className={`badge ${a.env === 'production' ? 'badge-red' : 'badge-blue'}`}>{a.env}</span></td>
                  <td><span className="mono text-xs text-muted">{a.registered}</span></td>
                  <td><span className="mono text-xs text-muted">{a.by}</span></td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="btn-ghost btn-sm">View</button>
                      <button className="btn-ghost btn-sm" style={{ color: 'var(--red)', borderColor: 'rgba(239,68,68,0.3)' }}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Register form */}
        <div className="panel" style={{ padding: 14 }}>
          <div className="section-label" style={{ marginBottom: 12 }}>Register New Alias</div>
          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            {[
              { key: 'canonicalId', placeholder: 'Canonical ID (svc-XXXXX)' },
              { key: 'current', placeholder: 'Current service name' },
              { key: 'alias', placeholder: 'Previous name (alias)' },
            ].map(({ key, placeholder }) => (
              <input
                key={key}
                placeholder={placeholder}
                value={(form as Record<string,string>)[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                style={{ padding: '5px 10px', flex: '1 1 180px' }}
              />
            ))}
            <select value={form.env} onChange={e => setForm(f => ({ ...f, env: e.target.value }))} style={{ padding: '5px 10px' }}>
              {['production','staging','all'].map(o => <option key={o}>{o}</option>)}
            </select>
            <button type="submit" className="btn-primary">Register Alias</button>
          </form>
          {submitted && <div className="text-xs" style={{ color: 'var(--green)', marginTop: 8 }}>✓ Alias registered successfully</div>}
          <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)' }}>
            Aliases enable cross-incident context matching when services are renamed or restructured. Canonical IDs persist across renames.
          </div>
        </div>

        {/* Lineage visualization */}
        <div className="panel" style={{ padding: 14 }}>
          <div className="section-label" style={{ marginBottom: 12 }}>Rename Lineage · svc-00441</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ padding: '6px 12px', background: 'var(--surface-high)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>payments-svc</div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
              <div style={{ width: 50, height: 1, background: 'var(--accent)' }} />
              <span className="mono text-xs text-muted">2024-05-15 14:22</span>
            </div>
            <div style={{ padding: '6px 12px', background: 'var(--accent-dim)', border: '1px solid rgba(26,108,246,0.3)', borderRadius: 'var(--radius)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--accent)' }}>billing-svc <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>(current)</span></div>
          </div>
          <div className="text-xs text-muted" style={{ marginTop: 10 }}>
            Used in 2 incident reconstructions: <span className="mono" style={{ color: 'var(--accent)' }}>INC-2024-0847</span>, <span className="mono" style={{ color: 'var(--accent)' }}>INC-2023-1204</span>
          </div>
        </div>
      </div>
    </div>
  );
}
