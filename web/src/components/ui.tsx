// Shared micro-components
export function ConfBar({ value, className = '' }: { value: number; className?: string }) {
  const tier = value >= 80 ? 'high' : value >= 50 ? 'mid' : 'low';
  return (
    <div className={`conf-bar-wrap ${className}`}>
      <div className="conf-bar-track">
        <div className={`conf-bar-fill ${tier}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs mono" style={{ color: tier === 'high' ? 'var(--green)' : tier === 'mid' ? 'var(--amber)' : 'var(--red)', minWidth: 32, textAlign: 'right' }}>
        {value}%
      </span>
    </div>
  );
}

const KIND_META: Record<string, { label: string; cls: string; badgeCls: string }> = {
  deploy:      { label: 'DEPLOY',      cls: 'ev-deploy',      badgeCls: 'badge-indigo' },
  log:         { label: 'LOG',         cls: 'ev-log',         badgeCls: 'badge-gray'   },
  metric:      { label: 'METRIC',      cls: 'ev-metric',      badgeCls: 'badge-amber'  },
  trace:       { label: 'TRACE',       cls: 'ev-trace',       badgeCls: 'badge-cyan'   },
  topology:    { label: 'TOPOLOGY',    cls: 'ev-topology',    badgeCls: 'badge-purple' },
  remediation: { label: 'REMEDIATION', cls: 'ev-remediation', badgeCls: 'badge-green'  },
};

export function EventTypeBadge({ kind }: { kind: string }) {
  const m = KIND_META[kind] ?? { label: kind.toUpperCase(), cls: '', badgeCls: 'badge-gray' };
  return <span className={`badge ${m.badgeCls}`}>{m.label}</span>;
}

export function EventBorderClass(kind: string) {
  return KIND_META[kind]?.cls ?? '';
}

export function SeverityBadge({ sev }: { sev: string }) {
  const map: Record<string, string> = { CRITICAL: 'badge-red', HIGH: 'badge-amber', MEDIUM: 'badge-blue', LOW: 'badge-gray' };
  return <span className={`badge ${map[sev] ?? 'badge-gray'}`}>{sev}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = { ACTIVE: 'badge-red', RESOLVED: 'badge-green', DEGRADED: 'badge-amber' };
  return <span className={`badge ${map[status] ?? 'badge-gray'}`}>{status}</span>;
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
      {message}
    </div>
  );
}

export function LoadingState({ message = 'Loading…' }: { message?: string }) {
  return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
      <div className="spinner" style={{ margin: '0 auto 12px' }} />
      {message}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div style={{ padding: 20, background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 'var(--radius)', color: 'var(--red)', fontSize: 12 }}>
      {message}
    </div>
  );
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
      <div>
        <h1 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 2 }}>{title}</h1>
        {subtitle && <div className="text-xs text-muted mono">{subtitle}</div>}
      </div>
      {right && <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>{right}</div>}
    </div>
  );
}
