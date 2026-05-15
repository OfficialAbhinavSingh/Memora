import { useState } from 'react';
import { DEMO_REMEDIATIONS } from '../data/mockData';
import { ConfBar, PageHeader } from '../components/ui';

export default function Remediations() {
  const [selected, setSelected] = useState(0);
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const rem = DEMO_REMEDIATIONS[selected];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader title="Remediation Suggestions" subtitle="INC-2024-0847 · billing-svc · 3 suggestions ranked by confidence" />

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
        {/* Left list */}
        <div style={{ width: '50%', borderRight: '1px solid var(--border)', overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {DEMO_REMEDIATIONS.map((r, i) => (
            <div
              key={r.rank}
              onClick={() => setSelected(i)}
              className="panel"
              style={{
                padding: 12, cursor: 'pointer',
                borderLeft: `3px solid ${i === selected ? 'var(--accent)' : 'transparent'}`,
                background: i === selected ? 'var(--surface-high)' : 'var(--surface)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-heading)' }}>#{r.rank} {r.title}</span>
                <span className={`badge badge-${r.labelColor}`}>{r.label}</span>
              </div>
              <ConfBar value={r.confidence} />
              <div className="text-xs text-muted" style={{ margin: '6px 0' }}>{r.history}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                {r.tags.map(t => <span key={t} className="badge badge-gray">{t}</span>)}
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {(['worked','failed','unsure'] as const).map(o => (
                  <button
                    key={o}
                    className="btn-ghost btn-sm"
                    style={feedback[i] === o ? { background: 'var(--accent-dim)', borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}
                    onClick={e => { e.stopPropagation(); setFeedback(f => ({ ...f, [i]: o })); }}
                  >
                    {o === 'worked' ? '✓ Worked' : o === 'failed' ? '✗ Failed' : '? Unsure'}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Right detail */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 600, color: 'var(--text-heading)', fontSize: 14 }}>{rem.title}</div>
            <span className={`badge badge-${rem.labelColor}`}>{rem.label}</span>
          </div>
          <ConfBar value={rem.confidence} />

          <div className="panel" style={{ padding: 12 }}>
            <div className="section-label" style={{ marginBottom: 8 }}>Execution Steps</div>
            <ol style={{ paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {rem.steps.map((step, i) => (
                <li key={i} style={{ fontSize: 12, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-body)', lineHeight: 1.6 }}>{step}</li>
              ))}
            </ol>
          </div>

          <div className="panel" style={{ padding: 12 }}>
            <div className="section-label" style={{ marginBottom: 6 }}>Historical Basis</div>
            <div style={{ fontSize: 12, color: 'var(--text-body)' }}>{rem.history}</div>
          </div>

          <div className="panel" style={{ padding: 12 }}>
            <div className="section-label" style={{ marginBottom: 6 }}>Risks</div>
            {rem.risks.map((risk, i) => (
              <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                <span style={{ color: 'var(--amber)', flexShrink: 0 }}>⚠</span>
                <span style={{ fontSize: 12, color: 'var(--text-body)' }}>{risk}</span>
              </div>
            ))}
          </div>

          <div className="panel" style={{ padding: 12 }}>
            <div className="section-label" style={{ marginBottom: 8 }}>Feedback</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>How did this remediation perform?</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['worked','failed','unsure'] as const).map(o => (
                <button
                  key={o}
                  className="btn-ghost"
                  style={feedback[selected] === o ? { background: 'var(--accent-dim)', borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}
                  onClick={() => setFeedback(f => ({ ...f, [selected]: o }))}
                >
                  {o === 'worked' ? '✓ Worked' : o === 'failed' ? '✗ Failed' : '? Unsure'}
                </button>
              ))}
            </div>
            {feedback[selected] && <div className="text-xs text-muted" style={{ marginTop: 8 }}>Feedback recorded · Thank you</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
