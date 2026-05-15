import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, History, GitBranch, Network, Zap,
  ShieldCheck, Activity, Share2, BarChart3,
} from 'lucide-react';
import './AppShell.css';

const NAV = [
  { to: '/',           label: 'Incident Workspace', icon: LayoutDashboard },
  { to: '/history',    label: 'Incident History',   icon: History },
  { to: '/timeline',   label: 'Investigation Timeline', icon: Activity },
  { to: '/causal',     label: 'Causal Chain',       icon: GitBranch },
  { to: '/similar',    label: 'Similar Incidents',  icon: Network },
  { to: '/remediations', label: 'Remediations',     icon: Zap },
  { to: '/topology',   label: 'Topology Aliases',   icon: Share2 },
  { to: '/benchmark',  label: 'Benchmark Results',  icon: BarChart3 },
  { to: '/graphs',     label: 'Knowledge Graphs',   icon: Network },
  { to: '/health',     label: 'System Health',      icon: ShieldCheck },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="sidebar-logo">
          <span className="mono" style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 13 }}>PCE</span>
          <span className="text-muted text-xs" style={{ marginLeft: 6 }}>v1</span>
        </div>
        <div className="sidebar-nav">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <Icon size={14} />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>
        <div className="sidebar-footer">
          <span className="status-dot healthy" />
          <span className="text-xs text-muted">API healthy</span>
        </div>
      </nav>
      <main className="content">{children}</main>
    </div>
  );
}
