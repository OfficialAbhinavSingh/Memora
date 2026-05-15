CREATE TABLE IF NOT EXISTS telemetry_events
(
    event_id String,
    ts DateTime64(3, 'UTC'),
    kind LowCardinality(String),
    tenant_id String,
    environment LowCardinality(String),
    service_name String,
    canonical_service_id String,
    incident_id String,
    trace_id String,
    entities Array(String),
    attributes String,
    raw_ref String,
    provenance String
)
ENGINE = MergeTree
PARTITION BY toDate(ts)
ORDER BY (tenant_id, environment, service_name, ts, event_id);
