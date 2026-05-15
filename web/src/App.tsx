import { Routes, Route } from 'react-router-dom';
import './App.css';
import AppShell from './components/AppShell';
import IncidentWorkspace from './pages/IncidentWorkspace';
import IncidentHistory from './pages/IncidentHistory';
import InvestigationTimeline from './pages/InvestigationTimeline';
import CausalChain from './pages/CausalChain';
import SimilarIncidents from './pages/SimilarIncidents';
import Remediations from './pages/Remediations';
import TopologyAliases from './pages/TopologyAliases';
import SystemHealth from './pages/SystemHealth';
import BenchmarkResults from './pages/BenchmarkResults';
import GraphVisualization from './pages/GraphVisualization';

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/"             element={<IncidentWorkspace />} />
        <Route path="/history"      element={<IncidentHistory />} />
        <Route path="/timeline"     element={<InvestigationTimeline />} />
        <Route path="/causal"       element={<CausalChain />} />
        <Route path="/similar"      element={<SimilarIncidents />} />
        <Route path="/remediations" element={<Remediations />} />
        <Route path="/topology"     element={<TopologyAliases />} />
        <Route path="/benchmark"    element={<BenchmarkResults />} />
        <Route path="/graphs"       element={<GraphVisualization />} />
        <Route path="/health"       element={<SystemHealth />} />
      </Routes>
    </AppShell>
  );
}
