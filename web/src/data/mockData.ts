// Mock data for billing-svc incident demo scenario
export const DEMO_INCIDENT = {
  id: 'INC-2024-0847',
  service: 'billing-svc',
  severity: 'CRITICAL' as const,
  title: 'billing-svc latency spike + checkout-api timeouts',
  startedAgo: '14m ago',
  environment: 'production',
  tenantId: 'tenant-prod-001',
  renamedFrom: 'payments-svc',
  deployTime: '14:22 UTC',
  confidence: 82,
  explain: 'billing-svc experienced a latency spike 3 minutes after the 14:22 deploy. checkout-api began reporting timeout errors at P99 > 2000ms. System detected topology alias: payments-svc maps to billing-svc (canonical_id: svc-00441). A prior incident (INC-2023-1204) with identical causal pattern was resolved via rollback. Rollback remediation is suggested with high confidence.',
};

export const DEMO_EVENTS = [
  { id: 'evt-001', ts: '14:22:04', kind: 'deploy',      service: 'billing-svc',  desc: 'Deploy v2.4.1 triggered by ci/cd-pipeline-889 (payments-svc renamed, billing config v2)', meta: 'commit: a3f2c1d', critical: false },
  { id: 'evt-002', ts: '14:22:31', kind: 'topology',    service: 'billing-svc',  desc: 'Alias registered: payments-svc → billing-svc (canonical_id: svc-00441)', meta: '', critical: false },
  { id: 'evt-003', ts: '14:24:11', kind: 'metric',      service: 'billing-svc',  desc: 'P95 latency: 340ms → 892ms (+162%)', meta: 'threshold: 800ms breached', critical: false },
  { id: 'evt-004', ts: '14:24:31', kind: 'metric',      service: 'billing-svc',  desc: 'P99 latency: 890ms → 2100ms (+136%)', meta: 'CRITICAL threshold breached', critical: true },
  { id: 'evt-005', ts: '14:25:02', kind: 'log',         service: 'checkout-api', desc: 'ERROR upstream timeout billing-svc:8080 deadline exceeded after 2000ms', meta: 'trace: 4f8a91b2', critical: true },
  { id: 'evt-006', ts: '14:25:15', kind: 'metric',      service: 'checkout-api', desc: 'Error rate: 1.2% → 12.3% (+925%)', meta: 'critical threshold exceeded', critical: true },
  { id: 'evt-007', ts: '14:25:33', kind: 'trace',       service: 'checkout-api → billing-svc', desc: 'Span timeout: checkout.place_order (duration: 2041ms, expected <500ms)', meta: 'trace: 4f8a91b2', critical: false },
  { id: 'evt-008', ts: '14:25:48', kind: 'log',         service: 'checkout-api', desc: 'ERROR upstream timeout billing-svc:8080 retry 1/3 failed', meta: 'trace: 5c2d84e1', critical: false },
  { id: 'evt-009', ts: '14:26:01', kind: 'topology',    service: 'billing-svc',  desc: 'Health check probe: /health returned 503 (connection pool exhausted)', meta: '', critical: false },
  { id: 'evt-010', ts: '14:26:15', kind: 'log',         service: 'billing-svc',  desc: 'WARN connection pool exhausted: active=48 max=50 waiting=12', meta: '', critical: false },
  { id: 'evt-011', ts: '14:26:30', kind: 'metric',      service: 'billing-svc',  desc: 'Connection pool utilization: 96%', meta: 'threshold: 90% breached', critical: false },
  { id: 'evt-012', ts: '14:27:00', kind: 'log',         service: 'billing-svc',  desc: 'ERROR request queue overflow: dropping requests (queue_size=200)', meta: '', critical: true },
  { id: 'evt-013', ts: '14:28:00', kind: 'remediation', service: 'billing-svc',  desc: 'Suggested: rollback to v2.3.9 — confidence 87% (based on INC-2023-1204)', meta: '', critical: false },
];

export const DEMO_CAUSAL_CHAIN = [
  {
    id: 'cc-1',
    label: 'ROOT CAUSE (inferred)',
    event: 'Deploy v2.4.1 · billing-svc · 14:22:04 UTC',
    kind: 'deploy',
    confidence: 89,
    description: 'New billing configuration introduced connection pool limit of 50 (previously 200). payments-svc renamed to billing-svc in this deploy.',
    evidence: 'commit a3f2c1d · billing-config.yaml diff · pool_max: 200→50',
  },
  {
    id: 'cc-2',
    label: 'EFFECT 1',
    event: 'billing-svc connection pool exhaustion · 14:24:11 UTC',
    kind: 'metric',
    confidence: 91,
    description: 'P99 latency climbed from 120ms to 2100ms as connection pool filled under existing load.',
    evidence: 'metric: billing_svc_latency_p99 · metric: billing_svc_pool_active',
    edgeLabel: 'CAUSED',
    edgeConf: 87,
  },
  {
    id: 'cc-3',
    label: 'EFFECT 2 (CASCADING)',
    event: 'checkout-api timeout cascade · 14:25:02 UTC',
    kind: 'log',
    confidence: 94,
    description: 'checkout-api upstream calls to billing-svc:8080 timed out after 2000ms. Error rate escalated to 12.3%.',
    evidence: 'trace: 4f8a91b2 · error_rate: 12.3% · 47 timeout errors in 90s',
    edgeLabel: 'PROPAGATED TO',
    edgeConf: 94,
  },
];

export const DEMO_SIMILAR = [
  {
    id: 'INC-2023-1204',
    service: 'payments-svc (now billing-svc)',
    date: '2023-11-14 · 09:18 UTC',
    score: 93,
    rationale: 'Deploy config change, pool exhaustion, cascade to API gateway',
    resolution: 'Rollback → resolved in 8 min',
    duration: '23 min',
    comparison: {
      trigger: 'Deploy v1.8.3',
      configChange: 'pool_max: 500→50',
      latencySpike: 'P99: 120ms→1800ms',
      cascadeTo: 'api-gateway',
      timeToDetect: '2m 14s',
      resolution: 'Rollback v1.8.2',
      outcome: '✓ Resolved in 8 min',
    },
  },
  {
    id: 'INC-2024-0312',
    service: 'billing-svc',
    date: '2024-02-28 · 16:44 UTC',
    score: 71,
    rationale: 'Latency spike, checkout-api timeouts, different root cause (DB slowdown)',
    resolution: 'Config patch → resolved in 34 min',
    duration: '51 min',
  },
  {
    id: 'INC-2023-0891',
    service: 'order-svc',
    date: '2023-08-03 · 11:30 UTC',
    score: 58,
    rationale: 'Connection pool pattern match, different service tree',
    resolution: 'Scale + restart → 18 min',
    duration: '42 min',
  },
];

export const DEMO_REMEDIATIONS = [
  {
    rank: 1,
    title: 'Rollback billing-svc to v2.3.9',
    confidence: 87,
    label: 'RECOMMENDED',
    labelColor: 'green' as const,
    history: 'Resolved INC-2023-1204 · 8 min · 0 recurrences in 90 days',
    command: 'kubectl rollout undo deployment/billing-svc --to-revision=14',
    tags: ['rollback', 'deploy-related', 'high-confidence'],
    steps: [
      'Verify current rollout: kubectl rollout status deployment/billing-svc',
      'Identify revision: kubectl rollout history deployment/billing-svc',
      'Execute rollback: kubectl rollout undo deployment/billing-svc --to-revision=14',
      'Monitor recovery: watch kubectl get pods -l app=billing-svc',
      'Confirm latency normalization (target: P99 < 200ms)',
    ],
    risks: [
      'Brief 30-60s service disruption during rollout transition',
      'v2.3.9 does not include billing-config schema updates from v2.4.1 — verify config compat before rollback',
    ],
  },
  {
    rank: 2,
    title: 'Scale billing-svc replicas to 6',
    confidence: 54,
    label: 'POSSIBLE',
    labelColor: 'amber' as const,
    history: 'Resolved INC-2024-0312 (partial) · 34 min · with config patch also applied',
    command: 'kubectl scale deployment/billing-svc --replicas=6',
    tags: ['scaling', 'capacity', 'medium-confidence'],
    steps: [
      'Check current replica count: kubectl get deployment billing-svc',
      'Scale up: kubectl scale deployment/billing-svc --replicas=6',
      'Monitor pod readiness: kubectl rollout status deployment/billing-svc',
      'Watch error rate: kubectl top pods -l app=billing-svc',
    ],
    risks: ['Does not address root cause (pool_max config). May only buy time.'],
  },
  {
    rank: 3,
    title: 'Update billing-config pool_max to 200',
    confidence: 41,
    label: 'INVESTIGATE',
    labelColor: 'gray' as const,
    history: 'No direct match — inferred from config diff analysis',
    command: 'kubectl edit configmap billing-config → pool_max: 200',
    tags: ['config-patch', 'low-confidence', 'manual'],
    steps: [
      'Inspect current config: kubectl get configmap billing-config -o yaml',
      'Edit pool_max: kubectl edit configmap billing-config',
      'Set pool_max: 200',
      'Restart billing-svc pods to pick up config change',
    ],
    risks: ['Manual config edit risk. Requires validation against v2.4.1 schema.'],
  },
];

export const DEMO_ALIASES = [
  { canonicalId: 'svc-00441', current: 'billing-svc',       aliases: ['payments-svc'], env: 'production', registered: '2024-05-15 14:22 UTC', by: 'ci/cd-pipeline-889' },
  { canonicalId: 'svc-00312', current: 'auth-svc',          aliases: ['authentication-service'], env: 'production', registered: '2024-04-02 09:11 UTC', by: '@ops-team' },
  { canonicalId: 'svc-00198', current: 'order-svc',         aliases: ['orders-api', 'order-service'], env: 'staging', registered: '2024-03-18 16:40 UTC', by: '@platform-eng' },
  { canonicalId: 'svc-00091', current: 'notification-svc',  aliases: ['notify-service'], env: 'production', registered: '2024-01-07 11:20 UTC', by: '@infra-team' },
];

export const DEMO_INCIDENTS_HISTORY = [
  { id: 'INC-2024-0847', service: 'billing-svc',  severity: 'CRITICAL', status: 'ACTIVE',   started: '14:22 UTC today',   duration: '14m+', summary: 'Deploy-triggered latency spike + cascade' },
  { id: 'INC-2024-0312', service: 'billing-svc',  severity: 'HIGH',    status: 'RESOLVED', started: '2024-02-28 16:44',  duration: '51m',  summary: 'checkout-api timeout (DB slowdown)' },
  { id: 'INC-2023-1204', service: 'payments-svc', severity: 'CRITICAL', status: 'RESOLVED', started: '2023-11-14 09:18',  duration: '23m',  summary: 'Deploy config rollback (pool exhaustion)' },
  { id: 'INC-2023-0891', service: 'order-svc',    severity: 'HIGH',    status: 'RESOLVED', started: '2023-08-03 11:30',  duration: '42m',  summary: 'Connection pool pattern match' },
  { id: 'INC-2023-0445', service: 'auth-svc',     severity: 'MEDIUM',  status: 'RESOLVED', started: '2023-05-12 08:05',  duration: '18m',  summary: 'Token validation latency spike' },
];

export const DEMO_HEALTH = {
  health: { status: 'HEALTHY', latency: 4, uptime: 99.97 },
  readiness: { status: 'READY', latency: 6, deps: { postgres: true, redis: true, event_store: true } },
  metrics: {
    events_ingested_total: { value: 48291, delta: '+1,243 today' },
    reconstructions_total: { value: 1847,  delta: '+12 today' },
    incidents_tracked:     { value: 394,   delta: '3 active' },
    aliases_registered:    { value: 4,     delta: '0 today' },
    avg_reconstruction_ms: { value: '342ms', delta: 'p95: 890ms' },
    feedback_outcomes:     { value: 723,   delta: '87% positive' },
    pattern_matches_today: { value: 34,    delta: '3 high-confidence' },
    api_error_rate:        { value: '0.02%', delta: 'Last 1h' },
  },
  recentCalls: [
    { ts: '15:33:14', endpoint: '/v1/context/reconstruct',             method: 'POST', status: 200, latency: '312ms' },
    { ts: '15:33:09', endpoint: '/v1/incidents/INC-2024-0847/memory', method: 'GET',  status: 200, latency: '28ms'  },
    { ts: '15:33:05', endpoint: '/v1/feedback/remediation-outcome',   method: 'POST', status: 200, latency: '14ms'  },
    { ts: '15:32:58', endpoint: '/v1/topology/alias',                 method: 'POST', status: 200, latency: '22ms'  },
    { ts: '15:32:41', endpoint: '/v1/ingest/events',                  method: 'POST', status: 200, latency: '89ms'  },
    { ts: '15:32:30', endpoint: '/v1/context/reconstruct',             method: 'POST', status: 200, latency: '445ms' },
    { ts: '15:32:11', endpoint: '/v1/metrics',                        method: 'GET',  status: 200, latency: '6ms'   },
    { ts: '15:31:55', endpoint: '/v1/health',                         method: 'GET',  status: 200, latency: '4ms'   },
  ],
};
