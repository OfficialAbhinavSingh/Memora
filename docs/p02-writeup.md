# Memora — Persistent Context Engine for Autonomous SRE
*Anvil P-02 · `anvil-2026-p02-L3-final`*

## L3 Final Benchmark Result

| Axis | Weight | Score | Contribution |
|---|---:|---:|---:|
| `recall@5` | 0.30 | 0.144 | 0.043 |
| `precision@5_mean` | 0.15 | 0.141 | 0.021 |
| `remediation_acc` | 0.20 | 0.448 | 0.090 |
| `latency_p95_ms` (62 ms vs 2000 ms budget) | 0.15 | 1.000 | 0.150 |
| `manual_context` | 0.10 | panel | — |
| `manual_explain` | 0.10 | panel | — |
| **Weighted automated** | **0.80** | | **0.3039** |

Generator: 30 services · 21 days · 80 topology mutations (cascading renames **on**) · 60 train + 25 eval incidents · 8 families · 20 % decoy rate. Seeds: `[314159, 271828, 161803, 141421, 173205]` (public L3 placeholders).

## 1. Memory Representation

Memora treats operational telemetry as evidence for long-lived incident memory, not as isolated records for keyword search. Every event is normalized at ingest into a stable envelope of timestamp, kind, service, canonical service id, incident id, trace id, extracted entities, attributes, and provenance hash, then routed into three structures formed during ingestion:

- a **service alias graph** that records every rename as an undirected edge and exposes BFS-resolved canonical lookup,
- a **per-incident profile** (`_IncidentProfile`) that accumulates nearby deploys, anomaly metrics, failure logs, traces, and remediations, and
- a **service-keyed event index** for sub-millisecond temporal-window candidate generation at query time.

Profiles are formed during ingestion, not lazily during query. This matters for the official L3 harness, which ingests the entire training corpus once and then asks reconstruction queries only for held-out signals. The profile produces a topology-independent **behavioural signature** of the form `deploy|<5m|latency|timeout|callee|rollback|resolved`. Two incidents with the same shape key are operationally equivalent regardless of service names — this is the substrate that survives renames and dependency drift.

The engine is deliberately not a vector-search wrapper. There is no embedding model, no ANN index, no learned retriever. Every match is reproducible from the inputs and is fully inspectable.

## 2. Relationship Synthesis

Reconstruction is a five-stage pipeline executed inside `Engine.reconstruct_context`:

1. **Candidate generation** — pull events from a 30-min pre-signal / 15-min post-signal window via `_by_service` lookups against the alias-resolved canonical and the full alias closure.
2. **Related-event ranking** — score by lineage match, alias overlap, incident-id continuation, entity mention, anomaly strength, and temporal proximity to the signal.
3. **Causal chain synthesis** — emit ordered evidence edges: deploy → metric spike, deploy → failure log, metric spike → upstream failure, trace caller↔callee, failure log → remediation. Each edge stores `cause_event_id`, `effect_event_id`, `evidence`, `confidence`, and an ordering proof; the schema fields the harness expects, plus extra audit fields for manual judging.
4. **Similar-incident matching** — for every historical profile, compute (a) shape-key score (binary) and Jaccard-weighted component score across `metric_class`, `log_class`, `trace_class`, `remediation_types`, `delay_bucket`, `has_deploy`, `has_remediation`, `resolved`; (b) lineage score from canonical / alias overlap; (c) trigger-token agreement.
5. **Remediation transfer** — rank historical remediations by lineage match, shape match, age decay, and the success/failure ledger; remap the target service through the alias graph so a `payments-svc` rollback can be transferred to the renamed `ledger-v2`.

The whole pipeline is bounded — fast mode caps related events at 10 and similar incidents at 5, which is what keeps the L3 worst-seed p95 at **62 ms**.

## 3. Drift Handling Strategy

The single biggest test in P-02 is whether the engine can recognise a recurring family when the underlying service has been renamed. L3 makes this strictly harder by enabling **cascading renames** — the same canonical service can be renamed two to four times across the 21-day timeline (`payments-svc → billing-svc → ledger-v2 → ledger-v2-r5`).

Memora handles this with three layers:

- **Alias graph BFS.** `_AliasGraph` stores renames as undirected edges. `resolve()` and `aliases()` both run a BFS from any input name, so every historical alias of a renamed service resolves to the same canonical and contributes evidence regardless of how many rename hops separate the train-time and eval-time names.
- **Behavioural shape matching.** When even the alias chain breaks (e.g. dependency drift renames the upstream caller, not the failing service), the topology-independent shape key still allows the historical incident to be found by behaviour: `deploy|<5m|latency|timeout|callee|rollback|resolved`.
- **Trigger-token inference.** When a signal arrives with only an alert string (`alert:svc-04-r3/latency_p99_ms>3000`), `_infer_service_from_trigger` extracts the service token before any service-keyed lookup, so even bare signals participate in alias resolution.

Contradictory remediation history is preserved rather than overwritten. Worked outcomes increase confidence; failed outcomes reduce it; older evidence decays. Each suggested remediation carries transfer proof: basis incident id, success/failure counts, target remapping through the alias graph, and the confidence contributors.

## 4. Latency Engineering

The benchmark adapter is intentionally stdlib-only, single-process, CPU-only — no NumPy beyond the harness, no embedding service, no graph database call-out. Three engineering decisions keep latency far under budget on the L3 stretch config (30 services × 21 days × ~76 k events × 25 query signals per seed):

- **Indexes built at ingest.** `_by_service`, `_by_incident`, and `_profiles` are built incrementally during `ingest()`, so reconstruction never scans the full event log.
- **Bounded windows.** Fast mode uses a 30-min pre-signal / 15-min post-signal window. Even with cascading aliases, candidate generation touches a small slice of state.
- **Cached signatures.** `_IncidentProfile.signature()` memoises the shape key and component sets, so each historical incident is re-scored in microseconds against the current profile.

Empirical L3 latency, across 5 seeds × 25 signals = 125 reconstructions:

```
worst-seed p95   = 62 ms          (vs 2000 ms fast-mode budget)
mean across all  = 45 ms
ingest cost      = 5.7 s for 53k train + 23k eval events (one-shot per seed)
```

This earns the full 0.150 latency contribution and leaves the remaining axes as the optimisation surface.

## 5. Continuous Learning & Auditability

Continuous learning is represented through three mechanisms, all reproducible and inspectable:

- **Profile formation.** Every new event recomputes the affected profile's signature; remediation events flip `resolved` and append to the historical ledger.
- **Feedback persistence.** `_feedback` stores every remediation observation with `(incident_id, action, target, outcome, observed_at, canonical_service_id)`. Future similar incidents reweight remediation candidates against this ledger.
- **Reasoning audit.** Every match in the returned `Context` carries lineage proof, shape-component scores, sequence audit, behavioural signature components, remediation history, and confidence contributors. The same `Context` flows through to the React workspace, so an operator inspects exactly what the engine did. This is the substrate the panel-graded `manual_context` and `manual_explain` axes evaluate.

## 6. Reproducibility

Single command, fixed seeds, locked stretch generator, deterministic adapter:

```bash
cd bench-p02-context
pip install -r requirements.txt
python run.py --adapter adapters.memora:Engine --out l3_report.json
```

The output `l3_report.json` is the submission artefact. Rerunning on judges' machines reproduces the per-seed and aggregated numbers above to the rounding precision shown in `metrics.aggregate`.

## 7. Honest Assessment

Latency and remediation-transfer behave well at the L3 stretch scale. Recall and precision are the active optimisation surface: the engine currently lands `recall@5 = 0.144` and `precision@5_mean = 0.141` against the L3 stretch (cascading renames + 20 % decoy rate). The alias-graph BFS, shape signature, and trigger inference are all in place; the next iteration tightens the candidate generation across deeper rename hops and the decoy-confidence threshold so unmatched signals return empty rather than confidently wrong. The architecture and the audit trail do not change — only the ranking calibration does.
