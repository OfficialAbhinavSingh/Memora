import { useEffect, useState } from 'react';
import './GraphVisualization.css';

interface TopoNode { id: string; canonical: string; type: string; group: string; families?: number[] }
interface TopoEdge { source: string; target: string; type: string }
interface CausalNode { id: string; kind: string; service: string; ts: string }
interface CausalEdge { source: string; target: string; evidence: string; confidence: number }
interface CausalChain { incident_id: string; family: number; service: string; trigger: string; nodes: CausalNode[]; edges: CausalEdge[] }
interface SimNode { id: string; family: number; type: string; score?: number; lineage?: number; shape?: number; service?: string }
interface SimEdge { source: string; target: string; score: number; correct: boolean }
interface SimGraph { incident_id: string; family: number; nodes: SimNode[]; edges: SimEdge[] }
interface Reconstruction { incident_id: string; family: number; service: string; trigger: string; recall_hit: boolean; precision: number; related_events_count: number; causal_edges_count: number; similar_count: number; confidence: number }
interface BenchTier { name: string; services: number; days: number; seeds: number; recall: number; precision: number; weighted: number; latency_p95: number }
interface PerSeed { seed: number; recall: number; precision: number; tier: string }
interface GraphData {
  topology: { nodes: TopoNode[]; edges: TopoEdge[] };
  causal_chains: CausalChain[];
  similar_incidents: SimGraph[];
  reconstructions: Reconstruction[];
  benchmark: { aggregate: Record<string, number>; tiers: BenchTier[]; per_seed: PerSeed[] };
}

const FAMILY_COLORS = ['#ef4444', '#22c55e', '#3b82f6', '#f59e0b', '#a78bfa', '#22d3ee', '#f472b6', '#84cc16', '#fb923c', '#6366f1'];
const KIND_COLORS: Record<string, string> = { deploy: '#6366f1', metric_anomaly: '#f59e0b', log: '#6b7280', trace: '#22d3ee', incident_signal: '#ef4444', remediation: '#22c55e', topology: '#a78bfa' };

function famColor(f: number) { return FAMILY_COLORS[f % FAMILY_COLORS.length]; }

// ── Topology Graph (Force-directed SVG) ──
function TopologyGraph({ nodes, edges }: { nodes: TopoNode[]; edges: TopoEdge[] }) {
  const W = 700, H = 420;
  const positions: Record<string, { x: number; y: number }> = {};
  const groups = [...new Set(nodes.map(n => n.group))].sort();
  nodes.forEach((n, i) => {
    const gi = groups.indexOf(n.group);
    const angle = (gi / groups.length) * Math.PI * 2 - Math.PI / 2;
    const r = n.type === 'renamed' ? 160 : 120;
    const jitter = (i % 3 - 1) * 20;
    positions[n.id] = { x: W / 2 + Math.cos(angle) * (r + jitter), y: H / 2 + Math.sin(angle) * (r + jitter) };
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="graph-svg">
      <defs>
        <marker id="arrow-topo" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="var(--accent)" /></marker>
      </defs>
      {edges.map((e, i) => {
        const s = positions[e.source], t = positions[e.target];
        if (!s || !t) return null;
        return <g key={i}><line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="var(--accent)" strokeWidth={2} strokeDasharray="6 3" markerEnd="url(#arrow-topo)" opacity={0.7} /><text x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 6} fill="var(--text-muted)" fontSize={9} textAnchor="middle">rename</text></g>;
      })}
      {nodes.map(n => {
        const p = positions[n.id];
        if (!p) return null;
        const color = n.type === 'renamed' ? 'var(--amber)' : n.type === 'standalone' ? 'var(--text-muted)' : 'var(--green)';
        const r = n.type === 'standalone' ? 16 : 20;
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={r} fill={`${color}22`} stroke={color} strokeWidth={2} />
            <text x={p.x} y={p.y + 1} fill="var(--text-heading)" fontSize={9} textAnchor="middle" dominantBaseline="middle" fontFamily="JetBrains Mono, monospace">{n.id}</text>
            {n.families && <text x={p.x} y={p.y + r + 10} fill="var(--text-muted)" fontSize={8} textAnchor="middle">fam: {n.families.join(',')}</text>}
          </g>
        );
      })}
      <g transform={`translate(${W - 140}, 10)`}>
        {[{ c: 'var(--green)', l: 'Original' }, { c: 'var(--amber)', l: 'Renamed' }, { c: 'var(--text-muted)', l: 'Standalone' }].map(({ c, l }, i) => (
          <g key={l} transform={`translate(0, ${i * 16})`}><circle cx={6} cy={6} r={5} fill={`${c}22`} stroke={c} strokeWidth={1.5} /><text x={16} y={10} fill="var(--text-body)" fontSize={9}>{l}</text></g>
        ))}
      </g>
    </svg>
  );
}

// ── Causal Chain Graph ──
function CausalGraph({ chain, active }: { chain: CausalChain; active: boolean }) {
  if (!active || !chain.nodes.length) return null;
  const W = 700, H = 300;
  const sorted = [...chain.nodes].sort((a, b) => (a.ts || '').localeCompare(b.ts || ''));
  const pos: Record<string, { x: number; y: number }> = {};
  sorted.forEach((n, i) => { pos[n.id] = { x: 60 + (i / Math.max(sorted.length - 1, 1)) * (W - 120), y: H / 2 + (i % 2 === 0 ? -30 : 30) }; });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="graph-svg">
      <defs><marker id="arrow-causal" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="var(--cyan)" /></marker></defs>
      {chain.edges.map((e, i) => {
        const s = pos[e.source], t = pos[e.target];
        if (!s || !t) return null;
        const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
        return <g key={i}><line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="var(--cyan)" strokeWidth={1.5} markerEnd="url(#arrow-causal)" opacity={0.6} /><text x={mx} y={my - 8} fill="var(--cyan)" fontSize={8} textAnchor="middle" opacity={0.8}>{e.evidence}</text><text x={mx} y={my + 10} fill="var(--text-muted)" fontSize={7} textAnchor="middle">{(e.confidence * 100).toFixed(0)}%</text></g>;
      })}
      {sorted.map(n => {
        const p = pos[n.id]; if (!p) return null;
        const color = KIND_COLORS[n.kind] || '#6b7280';
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={18} fill={`${color}22`} stroke={color} strokeWidth={2} />
            <text x={p.x} y={p.y - 2} fill="var(--text-heading)" fontSize={8} textAnchor="middle" fontWeight={600}>{n.kind.replace('_', ' ')}</text>
            <text x={p.x} y={p.y + 8} fill="var(--text-muted)" fontSize={7} textAnchor="middle">{n.service}</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Similar Incidents Radial Graph ──
function SimilarGraph({ graph }: { graph: SimGraph }) {
  const W = 360, H = 300, cx = W / 2, cy = H / 2;
  const query = graph.nodes.find(n => n.type === 'query')!;
  const matches = graph.nodes.filter(n => n.type === 'match');
  const mPos: Record<string, { x: number; y: number }> = {};
  matches.forEach((m, i) => {
    const angle = (i / matches.length) * Math.PI * 2 - Math.PI / 2;
    const dist = 80 + (1 - (m.score || 0)) * 40;
    mPos[m.id] = { x: cx + Math.cos(angle) * dist, y: cy + Math.sin(angle) * dist };
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="graph-svg graph-svg-sm">
      {graph.edges.map((e, i) => {
        const t = mPos[e.target]; if (!t) return null;
        return <line key={i} x1={cx} y1={cy} x2={t.x} y2={t.y} stroke={e.correct ? 'var(--green)' : 'var(--red)'} strokeWidth={e.correct ? 2 : 1} opacity={0.5} strokeDasharray={e.correct ? '' : '4 2'} />;
      })}
      <circle cx={cx} cy={cy} r={22} fill={`${famColor(graph.family)}33`} stroke={famColor(graph.family)} strokeWidth={2.5} />
      <text x={cx} y={cy - 3} fill="var(--text-heading)" fontSize={8} textAnchor="middle" fontWeight={700}>QUERY</text>
      <text x={cx} y={cy + 7} fill="var(--text-muted)" fontSize={7} textAnchor="middle">fam {graph.family}</text>
      {matches.map(m => {
        const p = mPos[m.id]; if (!p) return null;
        const correct = m.family === graph.family;
        return (
          <g key={m.id}>
            <circle cx={p.x} cy={p.y} r={16} fill={`${famColor(m.family)}22`} stroke={famColor(m.family)} strokeWidth={correct ? 2.5 : 1.5} />
            <text x={p.x} y={p.y - 2} fill="var(--text-heading)" fontSize={7} textAnchor="middle">fam {m.family}</text>
            <text x={p.x} y={p.y + 7} fill="var(--text-muted)" fontSize={7} textAnchor="middle">{((m.score || 0) * 100).toFixed(0)}%</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Benchmark Radar Chart ──
function RadarChart({ tiers }: { tiers: BenchTier[] }) {
  const W = 340, H = 300, cx = W / 2, cy = H / 2, R = 110;
  const axes = ['recall', 'precision', 'weighted'] as const;
  const axisLabel = ['Recall@5', 'Precision@5', 'Weighted Score'];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="graph-svg graph-svg-sm">
      {[0.25, 0.5, 0.75, 1.0].map(level => (
        <polygon key={level} points={axes.map((_, i) => { const a = (i / axes.length) * Math.PI * 2 - Math.PI / 2; return `${cx + Math.cos(a) * R * level},${cy + Math.sin(a) * R * level}`; }).join(' ')} fill="none" stroke="var(--border)" strokeWidth={0.5} />
      ))}
      {axes.map((_, i) => { const a = (i / axes.length) * Math.PI * 2 - Math.PI / 2; return <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a) * R} y2={cy + Math.sin(a) * R} stroke="var(--border)" strokeWidth={0.5} />; })}
      {axes.map((_, i) => { const a = (i / axes.length) * Math.PI * 2 - Math.PI / 2; return <text key={i} x={cx + Math.cos(a) * (R + 16)} y={cy + Math.sin(a) * (R + 16)} fill="var(--text-muted)" fontSize={9} textAnchor="middle" dominantBaseline="middle">{axisLabel[i]}</text>; })}
      {tiers.map((t, ti) => {
        const vals = [t.recall, t.precision, t.weighted];
        const pts = vals.map((v, i) => { const a = (i / axes.length) * Math.PI * 2 - Math.PI / 2; return `${cx + Math.cos(a) * R * v},${cy + Math.sin(a) * R * v}`; }).join(' ');
        const color = FAMILY_COLORS[ti % FAMILY_COLORS.length];
        return <polygon key={ti} points={pts} fill={`${color}18`} stroke={color} strokeWidth={1.5} />;
      })}
      <g transform={`translate(10, ${H - 10 - tiers.length * 14})`}>
        {tiers.map((t, i) => <g key={i} transform={`translate(0, ${i * 14})`}><rect width={8} height={8} rx={2} fill={FAMILY_COLORS[i % FAMILY_COLORS.length]} /><text x={12} y={8} fill="var(--text-body)" fontSize={8}>{t.name}</text></g>)}
      </g>
    </svg>
  );
}

// ── Precision Bar Chart ──
function PrecisionBars({ seeds }: { seeds: PerSeed[] }) {
  const W = 700, H = 200, barW = Math.min(32, (W - 60) / seeds.length - 4);
  const maxP = 1.0;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="graph-svg">
      {[0, 0.25, 0.5, 0.75, 1.0].map(v => (<g key={v}><line x1={50} y1={H - 30 - v / maxP * (H - 50)} x2={W - 10} y2={H - 30 - v / maxP * (H - 50)} stroke="var(--border)" strokeWidth={0.5} /><text x={45} y={H - 27 - v / maxP * (H - 50)} fill="var(--text-muted)" fontSize={8} textAnchor="end">{(v * 100).toFixed(0)}%</text></g>))}
      {seeds.map((s, i) => {
        const x = 55 + i * ((W - 70) / seeds.length);
        const h = (s.precision / maxP) * (H - 50);
        const color = s.precision >= 0.9 ? 'var(--green)' : s.precision >= 0.7 ? 'var(--accent)' : 'var(--amber)';
        return (
          <g key={i}>
            <rect x={x} y={H - 30 - h} width={barW} height={h} rx={2} fill={color} opacity={0.7} />
            <text x={x + barW / 2} y={H - 16} fill="var(--text-muted)" fontSize={7} textAnchor="middle" transform={`rotate(-45 ${x + barW / 2} ${H - 16})`}>{s.seed}</text>
            <text x={x + barW / 2} y={H - 33 - h} fill="var(--text-heading)" fontSize={7} textAnchor="middle">{(s.precision * 100).toFixed(0)}%</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Main Page ──
export default function GraphVisualization() {
  const [data, setData] = useState<GraphData | null>(null);
  const [activeChain, setActiveChain] = useState(0);
  const [activeTab, setActiveTab] = useState<'topology' | 'causal' | 'similar' | 'benchmark'>('topology');

  useEffect(() => { fetch('/graph-data.json').then(r => r.json()).then(setData).catch(console.error); }, []);

  if (!data) return <div style={{ padding: 32, color: 'var(--text-muted)' }}>Loading graph data...</div>;

  return (
    <div className="graph-page">
      <div className="graph-header">
        <h1 className="text-heading" style={{ fontSize: 18 }}>Knowledge Graph Visualization</h1>
        <p className="text-muted text-sm">Real data extracted from Memora engine — seed 42, 12 services, 7 days, 5 incident families</p>
      </div>

      <div className="graph-tabs">
        {(['topology', 'causal', 'similar', 'benchmark'] as const).map(tab => (
          <button key={tab} className={`graph-tab ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>
            {tab === 'topology' ? '🔗 Service Topology' : tab === 'causal' ? '⚡ Causal Chains' : tab === 'similar' ? '🔍 Incident Similarity' : '📊 Benchmark Analytics'}
          </button>
        ))}
      </div>

      {activeTab === 'topology' && (
        <div className="graph-section">
          <div className="panel" style={{ padding: 20 }}>
            <h2 className="section-label">Service Topology & Rename Chains</h2>
            <p className="text-muted text-xs" style={{ marginBottom: 12 }}>Nodes represent services. Dashed arrows show rename operations. Colors: <span style={{ color: 'var(--green)' }}>original</span> → <span style={{ color: 'var(--amber)' }}>renamed</span>. Family annotations show which incident families affected each service.</p>
            <TopologyGraph nodes={data.topology.nodes} edges={data.topology.edges} />
          </div>
          <div className="graph-stats-row">
            <div className="stat-card panel"><div className="stat-val">{data.topology.nodes.length}</div><div className="stat-label">Services</div></div>
            <div className="stat-card panel"><div className="stat-val">{data.topology.edges.length}</div><div className="stat-label">Rename Chains</div></div>
            <div className="stat-card panel"><div className="stat-val">{data.topology.nodes.filter(n => n.type === 'renamed').length}</div><div className="stat-label">Renamed Services</div></div>
            <div className="stat-card panel"><div className="stat-val">{new Set(data.topology.nodes.map(n => n.canonical)).size}</div><div className="stat-label">Canonical IDs</div></div>
          </div>
        </div>
      )}

      {activeTab === 'causal' && (
        <div className="graph-section">
          <div className="panel" style={{ padding: 20 }}>
            <h2 className="section-label">Causal Chain — Incident {data.causal_chains[activeChain]?.incident_id}</h2>
            <p className="text-muted text-xs" style={{ marginBottom: 8 }}>Directed graph of causal relationships: deploy → metric spike → failure → remediation. Edge labels show evidence type and confidence.</p>
            <div className="chain-selector">
              {data.causal_chains.map((c, i) => (
                <button key={i} className={`chain-btn ${i === activeChain ? 'active' : ''}`} onClick={() => setActiveChain(i)} style={{ borderColor: famColor(c.family) }}>
                  <span style={{ color: famColor(c.family) }}>●</span> {c.incident_id.split('-').slice(0, 2).join('-')} <span className="text-muted text-xs">F{c.family}</span>
                </button>
              ))}
            </div>
            <CausalGraph chain={data.causal_chains[activeChain]} active={true} />
          </div>
          <div className="panel" style={{ padding: 16 }}>
            <h2 className="section-label">Reconstruction Summary</h2>
            <table className="data-table">
              <thead><tr><th>Incident</th><th>Family</th><th>Service</th><th>Recall</th><th>Precision</th><th>Events</th><th>Causal</th><th>Confidence</th></tr></thead>
              <tbody>
                {data.reconstructions.map(r => (
                  <tr key={r.incident_id}>
                    <td className="mono text-xs">{r.incident_id}</td>
                    <td><span className="badge" style={{ background: `${famColor(r.family)}22`, color: famColor(r.family), border: `1px solid ${famColor(r.family)}44` }}>F{r.family}</span></td>
                    <td className="mono text-xs">{r.service}</td>
                    <td>{r.recall_hit ? <span className="badge badge-green">HIT</span> : <span className="badge badge-red">MISS</span>}</td>
                    <td className="mono">{(r.precision * 100).toFixed(0)}%</td>
                    <td>{r.related_events_count}</td>
                    <td>{r.causal_edges_count}</td>
                    <td><div className="conf-bar-wrap"><div className="conf-bar-track"><div className={`conf-bar-fill ${r.confidence > 0.7 ? 'high' : r.confidence > 0.4 ? 'mid' : 'low'}`} style={{ width: `${r.confidence * 100}%` }} /></div><span className="mono text-xs">{r.confidence.toFixed(2)}</span></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'similar' && (
        <div className="graph-section">
          <div className="panel" style={{ padding: 20 }}>
            <h2 className="section-label">Incident Similarity Graphs</h2>
            <p className="text-muted text-xs" style={{ marginBottom: 12 }}>Each graph shows a query incident (center) connected to its top-5 similar matches. <span style={{ color: 'var(--green)' }}>Green = correct family</span>, <span style={{ color: 'var(--red)' }}>Red = different family</span>. Closer nodes have higher similarity scores.</p>
          </div>
          <div className="similar-grid">
            {data.similar_incidents.map((g, i) => (
              <div key={i} className="panel similar-card">
                <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
                  <span className="mono text-xs" style={{ color: famColor(g.family) }}>{g.incident_id}</span>
                  <span className="badge" style={{ marginLeft: 8, background: `${famColor(g.family)}22`, color: famColor(g.family), border: `1px solid ${famColor(g.family)}44` }}>Family {g.family}</span>
                </div>
                <SimilarGraph graph={g} />
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'benchmark' && (
        <div className="graph-section">
          <div className="graph-bench-row">
            <div className="panel" style={{ padding: 20, flex: 1 }}>
              <h2 className="section-label">Performance Radar — All Tiers</h2>
              <RadarChart tiers={data.benchmark.tiers} />
            </div>
            <div className="panel" style={{ padding: 20, flex: 1 }}>
              <h2 className="section-label">Aggregate Metrics</h2>
              <div className="agg-grid">
                {Object.entries(data.benchmark.aggregate).map(([k, v]) => (
                  <div key={k} className="agg-card">
                    <div className="agg-val mono">{typeof v === 'number' && v < 10 ? v.toFixed(3) : v}</div>
                    <div className="agg-label">{k.replace(/_/g, ' ')}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 16 }}>
                <table className="data-table">
                  <thead><tr><th>Tier</th><th>Svcs</th><th>Days</th><th>Seeds</th><th>R@5</th><th>P@5</th><th>Score</th></tr></thead>
                  <tbody>{data.benchmark.tiers.map(t => (
                    <tr key={t.name}><td className="text-heading">{t.name}</td><td>{t.services}</td><td>{t.days}</td><td>{t.seeds}</td><td className="mono">{t.recall.toFixed(3)}</td><td className="mono">{t.precision.toFixed(3)}</td><td className="mono text-heading">{t.weighted.toFixed(3)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          </div>
          <div className="panel" style={{ padding: 20 }}>
            <h2 className="section-label">Precision@5 by Seed</h2>
            <PrecisionBars seeds={data.benchmark.per_seed} />
          </div>
        </div>
      )}
    </div>
  );
}
