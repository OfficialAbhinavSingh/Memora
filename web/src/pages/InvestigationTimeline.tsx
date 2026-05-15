import { useState } from 'react';
import { DEMO_EVENTS } from '../data/mockData';
import { EventTypeBadge, EventBorderClass, PageHeader } from '../components/ui';

const KINDS = ['deploy','log','metric','trace','topology','remediation'] as const;
const SERVICES = ['All Services','billing-svc','checkout-api','payments-svc (alias)'];

export default function InvestigationTimeline() {
  const [activeKinds, setActiveKinds] = useState<Set<string>>(new Set());
  const [service, setService] = useState('All Services');

  const toggle = (k: string) => setActiveKinds(s => {
    const n = new Set(s);
    if (n.has(k)) {
      n.delete(k);
    } else {
      n.add(k);
    }
    return n;
  });

  const filtered = DEMO_EVENTS.filter(ev => {
    if (activeKinds.size > 0 && !activeKinds.has(ev.kind)) return false;
    if (service !== 'All Services' && !ev.service.includes(service.replace(' (alias)',''))) return false;
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="Investigation Timeline"
        subtitle="INC-2024-0847 · billing-svc · Started 14:22 UTC"
        right={
          <button className="btn-ghost btn-sm">Export</button>
        }
      />

      {/* Filter bar */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {KINDS.map(k => {
          const active = activeKinds.has(k);
          const colorMap: Record<string,string> = { deploy:'var(--indigo)', log:'var(--text-muted)', metric:'var(--amber)', trace:'var(--cyan)', topology:'var(--purple)', remediation:'var(--green)' };
          return (
            <button
              key={k}
              onClick={() => toggle(k)}
              style={{
                padding: '3px 10px', fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
                background: active ? `${colorMap[k]}22` : 'transparent',
                border: `1px solid ${active ? colorMap[k] : 'var(--border)'}`,
                color: active ? colorMap[k] : 'var(--text-muted)',
                borderRadius: 'var(--radius)', cursor: 'pointer', letterSpacing: '0.04em',
              }}
            >
              {k}
            </button>
          );
        })}
        <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />
        <select value={service} onChange={e => setService(e.target.value)} style={{ padding: '3px 8px', fontSize: 12 }}>
          {SERVICES.map(s => <option key={s}>{s}</option>)}
        </select>
        <span className="text-xs text-muted mono" style={{ marginLeft: 'auto' }}>{filtered.length} events · spanning 6 minutes</span>
      </div>

      {/* Timeline */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
        <div style={{ position: 'relative', paddingLeft: 32 }}>
          {/* axis line */}
          <div style={{ position: 'absolute', left: 10, top: 0, bottom: 0, width: 1, background: 'var(--border)' }} />

          {filtered.map(ev => {
            const colorMap: Record<string,string> = { deploy:'var(--indigo)', log:'var(--text-muted)', metric:'var(--amber)', trace:'var(--cyan)', topology:'var(--purple)', remediation:'var(--green)' };
            const dotColor = colorMap[ev.kind] ?? 'var(--border)';
            return (
              <div key={ev.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 4, position: 'relative' }}>
                {/* dot */}
                <div style={{
                  position: 'absolute', left: -26, top: 11,
                  width: 8, height: 8, borderRadius: '50%',
                  background: dotColor, flexShrink: 0,
                  border: `1.5px solid var(--surface-low)`,
                }} />
                <div
                  className={EventBorderClass(ev.kind)}
                  style={{
                    flex: 1, display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 12px', borderRadius: 'var(--radius)',
                    background: ev.critical ? 'rgba(239,68,68,0.04)' : 'var(--surface)',
                    border: `1px solid ${ev.critical ? 'rgba(239,68,68,0.15)' : 'var(--border)'}`,
                  }}
                >
                  <span className="mono text-xs text-muted" style={{ minWidth: 80, flexShrink: 0 }}>{ev.ts} UTC</span>
                  <EventTypeBadge kind={ev.kind} />
                  <span className="mono text-xs" style={{ minWidth: 130, flexShrink: 0, color: 'var(--text-body)' }}>{ev.service}</span>
                  <span style={{ flex: 1, fontSize: 12, color: ev.critical ? 'var(--red)' : 'var(--text-body)' }}>{ev.desc}</span>
                  <span className="mono text-xs text-muted" style={{ flexShrink: 0 }}>{ev.meta}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Density chart */}
        <div style={{ marginTop: 24, padding: '10px 14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
          <div className="section-label" style={{ marginBottom: 8 }}>Event Density · 14:00–14:35 UTC</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 36 }}>
            {[1,0,0,1,0,1,2,0,3,4,5,6,4,3,2,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0].map((h, i) => (
              <div key={i} style={{
                flex: 1, height: `${Math.max(h * 15, 2)}px`,
                background: i >= 9 && i <= 15 ? 'var(--red)' : h > 0 ? 'var(--accent)' : 'var(--surface-high)',
                borderRadius: 1, opacity: h === 0 ? 0.3 : 1,
              }} />
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            <span className="mono text-xs text-muted">14:00</span>
            <span className="mono text-xs" style={{ color: 'var(--red)' }}>↑ peak 14:24–14:27</span>
            <span className="mono text-xs text-muted">14:35</span>
          </div>
        </div>
      </div>
    </div>
  );
}
