CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topology_aliases (
    tenant_id TEXT NOT NULL,
    environment TEXT NOT NULL,
    service_from TEXT NOT NULL,
    service_to TEXT NOT NULL,
    canonical_service_id TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, environment, service_from, service_to, observed_at)
);

CREATE TABLE IF NOT EXISTS remediation_feedback (
    incident_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    environment TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    outcome TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '',
    service_name TEXT NOT NULL DEFAULT '',
    canonical_service_id TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_memories (
    tenant_id TEXT NOT NULL,
    environment TEXT NOT NULL,
    incident_id TEXT PRIMARY KEY,
    signal JSONB NOT NULL,
    context JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS incident_memories_tenant_env_observed_idx
    ON incident_memories (tenant_id, environment, observed_at DESC);
