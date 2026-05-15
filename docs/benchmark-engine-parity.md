# Benchmark Engine Parity

The official Anvil P-02 score is produced by the stdlib-only Python adapter in
`bench/adapters/memora.py`. The production Go service keeps the same contracts
and vocabulary so the demo is not a separate invention.

## Contract Mapping

| Benchmark adapter concept | Production service concept | Purpose |
| --- | --- | --- |
| normalized event dict | telemetry envelope | preserves provenance, timestamp ordering, service/entity extraction |
| `_AliasGraph` | topology alias registry | maps renamed services to stable lineages |
| `_IncidentProfile` | incident memory record | incrementally forms long-lived operational memory during ingest |
| behavioral signature | incident shape fingerprint | compares deploy timing, anomaly class, trace role, log failure class, remediation type |
| behavior-first ranker | memory traversal policy | scores lineage, shape, trigger, temporal order, and remediation transfer before recall fallback |
| `_causal_edges` | relationship projection | emits inspectable cause/effect edges with evidence and ordering proof |
| `_feedback` | remediation feedback table | reinforces worked actions, penalizes failed actions, decays old evidence |
| `reconstruct_context` | `/v1/context/reconstruct` | compiles the required `Context` object |

## Required Context Shape

Both paths preserve the official output fields:

- `related_events`
- `causal_chain`
- `similar_past_incidents`
- `suggested_remediations`
- `confidence`
- `explain`

The Python adapter also adds optional audit fields inside matches, causal edges,
and remediation suggestions. These are ignored by the public scorer but useful
for manual judging and production debugging.

## Ranking Parity

The Python adapter's top-5 incident ranking maps directly to production memory
graph traversal:

- lineage score maps to service alias and canonical-service edges
- shape score maps to behavioral signature/cohort edges
- temporal score maps to ordered event relationships
- remediation score maps to feedback and outcome edges
- recall fallback maps to an explicit exploration policy, not a hidden heuristic

## Why Python Is The Scoring Path

The public harness runs local Python adapters, creates a fresh engine per seed,
and measures recall, remediation accuracy, and latency. For reproducibility the
adapter avoids external services, models, network calls, and non-stdlib
dependencies. The Go/API/UI stack demonstrates how the same memory substrate
would be operated as a service.
