import { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { ConfBar, ErrorState, LoadingState, PageHeader } from '../components/ui';

type SeedSummary = {
  'recall@5': number;
  'precision@5_mean': number;
  remediation_acc: number;
  latency_p95_ms: number;
  latency_mean_ms: number;
  n: number;
};

type SeedReport = {
  seed: number;
  n_train: number;
  n_eval: number;
  n_signals: number;
  ingest_ms: number;
  summary: SeedSummary;
};

type BenchmarkReport = {
  mode: string;
  seeds: number[];
  per_seed: SeedReport[];
  aggregated: SeedSummary & {
    n_seeds: number;
    n_signals_total: number;
  };
  score: {
    weighted_score: number;
    max_automated: number;
    axes: Record<string, number | null>;
  };
};

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function scorePct(value: number, max = 1) {
  return Math.round((value / max) * 100);
}

function fmtMs(value: number) {
  return `${value.toFixed(value >= 10 ? 0 : 2)} ms`;
}

function MetricCard({ label, value, detail, bar }: { label: string; value: string; detail: string; bar?: number }) {
  return (
    <div className="panel" style={{ padding: '12px 14px', minHeight: 96 }}>
      <div className="label-caps" style={{ marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 6 }}>{value}</div>
      {bar !== undefined && <ConfBar value={bar} />}
      <div className="text-xs text-muted" style={{ marginTop: 8 }}>{detail}</div>
    </div>
  );
}

export default function BenchmarkResults() {
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadReport() {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`/benchmark-report.json?ts=${Date.now()}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setReport(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load benchmark-report.json');
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/benchmark-report.json?ts=${Date.now()}`, { signal: controller.signal })
      .then(res => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then((payload: BenchmarkReport) => {
        setReport(payload);
        setError('');
      })
      .catch(err => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Could not load benchmark-report.json');
        setReport(null);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const summary = report?.aggregated;
  const weightedPercent = useMemo(() => {
    if (!report) return 0;
    return scorePct(report.score.weighted_score, report.score.max_automated);
  }, [report]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="Benchmark Results"
        subtitle="Official P-02 public harness artifact · web/public/benchmark-report.json"
        right={
          <button className="btn-primary" onClick={loadReport} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={12} /> {loading ? 'Loading' : 'Reload Report'}
          </button>
        }
      />

      <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {loading && <LoadingState message="Loading benchmark report..." />}
        {!loading && error && (
          <ErrorState message={`No benchmark report is being served yet. Run: powershell -ExecutionPolicy Bypass -File .\\bench\\run.ps1. Fetch error: ${error}`} />
        )}
        {!loading && summary && report && (
          <>
            <div className="panel" style={{ padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, alignItems: 'center' }}>
                <div>
                  <div className="section-label">P-02 Public Harness · {report.mode.toUpperCase()} Mode</div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-heading)', marginBottom: 8 }}>
                    {report.score.weighted_score.toFixed(4)} / {report.score.max_automated.toFixed(2)}
                  </div>
                  <div className="text-xs text-muted">
                    {summary.n_signals_total} eval signals · {summary.n_seeds} seeds · {report.seeds.join(', ')}
                  </div>
                </div>
                <div style={{ width: 320 }}>
                  <div className="text-xs text-muted" style={{ marginBottom: 6 }}>Weighted automated score</div>
                  <ConfBar value={weightedPercent} />
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(150px, 1fr))', gap: 12 }}>
              <MetricCard label="Recall@5" value={pct(summary['recall@5'])} detail="Same-family incident appears in top 5" bar={scorePct(summary['recall@5'])} />
              <MetricCard label="Precision@5" value={pct(summary['precision@5_mean'])} detail="Mean top-5 family precision" bar={scorePct(summary['precision@5_mean'])} />
              <MetricCard label="Remediation" value={pct(summary.remediation_acc)} detail="Correct action surfaced" bar={scorePct(summary.remediation_acc)} />
              <MetricCard label="p95 Latency" value={fmtMs(summary.latency_p95_ms)} detail="Fast budget: 2000 ms" bar={Math.max(0, Math.min(100, Math.round(100 - (summary.latency_p95_ms / 2000) * 100)))} />
              <MetricCard label="Mean Latency" value={fmtMs(summary.latency_mean_ms)} detail="Average reconstruction time" />
            </div>

            <div className="panel" style={{ overflow: 'hidden' }}>
              <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid var(--border)' }}>
                <span className="section-label">Per-Seed Results</span>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Seed</th>
                    <th>Signals</th>
                    <th>Train / Eval Events</th>
                    <th>Recall</th>
                    <th>Precision</th>
                    <th>Remediation</th>
                    <th>p95 Latency</th>
                    <th>Ingest</th>
                  </tr>
                </thead>
                <tbody>
                  {report.per_seed.map(seed => (
                    <tr key={seed.seed}>
                      <td><span className="mono text-xs" style={{ color: 'var(--text-heading)' }}>{seed.seed}</span></td>
                      <td>{seed.n_signals}</td>
                      <td><span className="mono text-xs text-muted">{seed.n_train} / {seed.n_eval}</span></td>
                      <td><span style={{ color: 'var(--green)' }}>{pct(seed.summary['recall@5'])}</span></td>
                      <td>{pct(seed.summary['precision@5_mean'])}</td>
                      <td><span style={{ color: 'var(--green)' }}>{pct(seed.summary.remediation_acc)}</span></td>
                      <td>{fmtMs(seed.summary.latency_p95_ms)}</td>
                      <td>{fmtMs(seed.ingest_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel" style={{ padding: 14 }}>
              <div className="section-label">Command Provenance</div>
              <div className="mono text-xs" style={{ color: 'var(--text-heading)', marginBottom: 8 }}>
                powershell -ExecutionPolicy Bypass -File .\bench\run.ps1
              </div>
              <div className="text-xs text-muted">
                The frontend displays the generated benchmark artifact. It does not run the benchmark in the browser.
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
