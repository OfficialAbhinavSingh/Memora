# Memora: Context Engine Implementation Details
**Anvil P-02 Benchmark Submission Writeup**

## 1. Memory Representation
Memora builds an incremental, event-driven memory model (`_IncidentProfile`) entirely in-memory during the `ingest()` phase. Rather than parsing raw telemetry queries during evaluation, Memora constructs a topology-independent **behavioral signature** for every incident sequence it observes. 
- During `ingest`, events tied to an incident ID are clustered.
- The `signature()` method caches a boolean and bucketed representation of the incident (e.g., `has_deploy`, `delay_bucket: 5-15m`, `metric_class: [latency, saturation]`, `log_class: [5xx]`).
- A `resolved` flag is tracked based on downstream remediation outcomes.

This allows the evaluation phase (`reconstruct_context`) to immediately perform lightning-fast similarity scoring against pre-computed behavioral hashes, dramatically lowering latency and satisfying the requirement that memory is formed during ingestion.

## 2. Relationship Synthesis
Causal relationships are deterministically synthesized without reliance on heavyweight external LLMs during the hot path. Instead, Memora uses time-windowed heuristics over the normalized telemetry stream:
- **Deploy → Metric Spike**: Found by searching for metrics breaching anomaly thresholds (e.g., latency > 200ms) within 60 minutes of a deployment on the same canonical service.
- **Metric Spike → Log Failure**: Links leading indicators (saturation/latency) to lagging indicators (5xx/timeouts) within a tight 30-minute window.
- **Trace Caller → Callee**: Cross-service latency propagates through distributed traces. Memora extracts the upstream/downstream linkage directly from `trace` spans to build causal edges.
- **Failure → Remediation**: Connects the end-state of the failure graph to the operational action taken to resolve it.

Edges are deduplicated and ranked by a static confidence heuristic that prioritizes explicit deployment changes and trace-verified network boundaries.

## 3. Drift Strategy
Services rename. Topologies shift. To survive dependency drift, Memora relies on an **Alias Graph** (Union-Find with BFS component resolution).
- When a `topology` event signals a `rename` (e.g., `payments-old` -> `billing-svc`), the graph unifies their identities.
- Historical incidents recorded under `payments-old` are resolved to the *current* canonical ID (`billing-svc`).
- During `reconstruct_context`, Memora checks historical incidents using the current alias lineage. If a historical remediation succeeded on `payments-old`, Memora dynamically rewrites the suggested remediation target to `billing-svc` for the active incident.

This ensures institutional knowledge isn't lost when services are rebranded or structurally mutated.

## 4. Latency Engineering
To meet the stringent <2s (fast) and <6s (deep) p95 benchmarks:
- **Pre-computation**: As mentioned in Section 1, signatures are built during ingest, shifting the O(N) event parsing out of the eval hot-path.
- **Bounded Windows**: Fast mode strictly filters related events to `[T-30m, T+15m]`, while deep mode looks back 4 hours. 
- **Efficient Indexing**: Events are indexed by `canonical_service_id` and `incident_id` in a `defaultdict`. Resolving candidates for evaluation avoids full-table scans.
- **Graph Optimization**: The alias resolution uses an in-memory queue-based BFS that evaluates in microseconds, caching canonical mappings.

## 5. Learning and Reinforcement
Remediation ranking is a continuous feedback loop:
- `remediation` events with outcomes (`resolved`, `success`, `failed`) adjust the internal confidence of historical actions.
- A **decay factor** is applied: successful actions age out gracefully (a 0.25 penalty scaled linearly over 365 days).
- Successful `rollback` actions strictly outrank failed `restart` attempts for incidents exhibiting identical behavioral signatures.
- If no confident historical remediation exists, a fallback heuristic infers safe actions (e.g., suggesting a rollback if the incident trigger mentions a deploy).
