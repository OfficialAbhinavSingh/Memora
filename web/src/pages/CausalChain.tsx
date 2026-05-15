import { DEMO_CAUSAL_CHAIN, DEMO_INCIDENT } from '../data/mockData';
import { ConfBar, EventTypeBadge, PageHeader } from '../components/ui';

export default function CausalChain() {
  const nodeColors: Record<string, string> = { 'ROOT CAUSE (inferred)': 'var(--red)', 'EFFECT 1': 'var(--amber)', 'EFFECT 2 (CASCADING)': 'var(--red)' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="Causal Chain"
        subtitle="INC-2024-0847 · billing-svc · Reconstructed context"
        right={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="text-xs text-muted">Overall confidence</span>
            <div style={{ width: 120 }}><ConfBar value={DEMO_INCIDENT.confidence} /></div>
          </div>
        }
      />

      <div style={{ flex: 1, overflow: 'auto', padding: 20, display: 'flex', gap: 20 }}>
        {/* Left: causal chain */}
        <div style={{ flex: '0 0 58%', display: 'flex', flexDirection: 'column', gap: 0 }}>
          {DEMO_CAUSAL_CHAIN.map((node, i) => (
            <div key={node.id}>
              {i > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0 8px 20px' }}>
                  <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span className="label-caps">{node.edgeLabel}</span>
                    <span className="mono text-xs" style={{ color: 'var(--accent)' }}>edge conf {node.edgeConf}%</span>
                  </div>
                </div>
              )}
              <div className="panel" style={{ padding: 14, borderLeft: `3px solid ${nodeColors[node.label] ?? 'var(--accent)'}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span className="label-caps" style={{ color: nodeColors[node.label] ?? 'var(--text-muted)' }}>{node.label}</span>
                  <EventTypeBadge kind={node.kind} />
                </div>
                <div style={{ fontWeight: 600, color: 'var(--text-heading)', fontSize: 13, marginBottom: 6 }}>{node.event}</div>
                <div style={{ fontSize: 12, color: 'var(--text-body)', marginBottom: 8, lineHeight: 1.6 }}>{node.description}</div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span className="mono text-xs text-muted">{node.evidence}</span>
                  <ConfBar value={node.confidence} />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Right: evidence panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="panel" style={{ padding: 14 }}>
            <div className="section-label">Evidence</div>
            <div style={{ padding: 10, background: 'var(--surface-low)', borderRadius: 'var(--radius)', marginBottom: 10, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7 }}>
              <div style={{ color: 'var(--red)', marginBottom: 4 }}>14:25:02 UTC checkout-api</div>
              <div>ERROR: upstream timeout billing-svc:8080</div>
              <div>deadline exceeded after 2000ms</div>
              <div style={{ marginTop: 6, color: 'var(--cyan)' }}>trace: 4f8a91b2</div>
            </div>
            <div style={{ fontSize: 12, marginBottom: 8 }}>
              <span className="badge badge-cyan" style={{ marginRight: 6 }}>SPAN</span>
              <span className="mono text-xs">checkout.place_order · 2041ms · TIMEOUT</span>
            </div>
            <div style={{ fontSize: 12 }}>
              <span className="badge badge-amber" style={{ marginRight: 6 }}>CONFIG DIFF</span>
              <span className="mono text-xs">billing-config.yaml · pool_max 200→50</span>
            </div>
          </div>

          <div className="panel" style={{ padding: 14 }}>
            <div className="section-label">Similar Chain in INC-2023-1204</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span className="badge badge-green">93% match</span>
              <span className="text-xs text-muted">Deploy with config change → pool exhaustion → upstream timeouts</span>
            </div>
            <div className="text-xs" style={{ color: 'var(--green)' }}>✓ Resolved via rollback in 8 minutes</div>
          </div>

          <div className="panel" style={{ padding: 14, borderColor: 'rgba(26,108,246,0.3)', borderWidth: 1 }}>
            <div className="section-label" style={{ color: 'var(--accent)' }}>Suggested Next Step</div>
            <div style={{ fontSize: 12, color: 'var(--text-body)', marginBottom: 12, lineHeight: 1.6 }}>
              Based on this causal chain, rollback to v2.3.9 is the highest-confidence action. This directly reverses the pool limit change.
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-primary">Begin Rollback</button>
              <button className="btn-ghost">View Remediation Panel</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
