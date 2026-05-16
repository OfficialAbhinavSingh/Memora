# Memora · Anvil P-02 — 5-Minute Demo Script

> **Hard requirement:** the recording must show the `★★★ A N V I L · P-02 · L3 FINAL BENCH ★★★` banner with release tag `anvil-2026-p02-L3-final`. We do that on screen between 0:30 and 1:30.

Pre-flight checklist (do **before** hitting record):
- [ ] Terminal in `bench-p02-context/`, virtualenv active, `numpy` installed.
- [ ] Browser already on `http://localhost:5173/` with the React workspace built (`npm run dev` running in a side terminal).
- [ ] Editor with three tabs pre-opened: `bench/adapters/memora.py`, `docs/p02-writeup.md`, `bench-p02-context/l3_report.json`.
- [ ] Mic check, screen at 1080p, hide notifications.

---

## 0:00 — 0:30 · Hook

**Show:** clean editor with `bench/adapters/memora.py` open, scrolled to the `Engine` class.

**Say:**
> "I'm presenting Memora — a Persistent Context Engine for autonomous SRE, submitted to Anvil P-02. Memora is not embedding-based retrieval. It forms structured incident memory at ingest time and reconstructs evidence-backed context at incident time. Every match has a reasoning audit attached — lineage, shape, temporal proof, and remediation history."

---

## 0:30 — 1:30 · Run the L3 Final Benchmark Live

**Show:** terminal in `bench-p02-context/`. Type and run:

```bash
python run.py --adapter adapters.memora:Engine --out l3_report.json
```

**While the banner prints:**
> "This is the only bench that counts for P-02 — the L3 final. Single command, single output. The stretch generator is locked: 30 services, 21 days, 80 topology mutations with cascading renames on, 60 plus 25 incidents across 8 families, 20 % decoy rate, five council seeds. Full multi-seed run takes about forty seconds on this laptop, CPU only, no GPU."

**When the closing banner appears:**
> "Final L3 score: zero point three zero three nine out of zero point eight. Latency p95 is 62 milliseconds against a 2000 millisecond budget — that earns the full latency axis. Recall and precision are the active optimisation surface; the architecture defends them in a moment."

---

## 1:30 — 2:15 · Inspect the Submission JSON

**Show:** open `bench-p02-context/l3_report.json`. Scroll to `aggregated` and `score`.

**Say:**
> "This JSON is the submission artefact. It includes the L3 release tag, the adapter SHA-256, the per-incident breakdown for every seed, the per-axis weighted contribution, and the aggregated automated score. The council can re-run this on judges' machines and reproduce the numbers — the engine is deterministic and stdlib-only."

**Highlight on screen:** `"l3_version": "anvil-2026-p02-L3-final"` and `"adapter_sha256"`.

---

## 2:15 — 3:00 · Architecture in 45 Seconds

**Show:** `bench/adapters/memora.py` — scroll to the `_AliasGraph` class, then to `_IncidentProfile.signature()`.

**Say:**
> "Three structures are built at ingest. The alias graph stores every rename as an undirected edge — `resolve` and `aliases` both run BFS, so a service renamed four times still resolves to one canonical identity. The incident profile accumulates deploy, anomaly, log, trace, and remediation evidence into a topology-independent shape key like `deploy bar less-than-five-minutes bar latency bar timeout bar callee bar rollback bar resolved`. Two incidents with the same shape key are operationally equivalent regardless of service names. And a service-keyed event index makes candidate generation a sub-millisecond lookup."

---

## 3:00 — 3:45 · Topology Drift, Live

**Show:** browser → React workspace → **Topology Aliases** page.

**Demonstrate:** click through a chained rename, e.g. `payments-svc → billing-svc → ledger-v2 → ledger-v2-r5`. All four nodes highlight as aliases of one canonical.

**Say:**
> "L3 makes topology drift strictly harder than L2 — cascading renames mean a single canonical service can be renamed two to four times across the timeline. A string-matching baseline is dead on arrival. Memora's alias graph BFS resolves any historical alias to the current canonical, so a payments-svc rollback from day three can be transferred to a ledger-v2-r5 incident on day twenty."

**Cut to:** **Similar Incidents** page on the same workspace.

**Say:**
> "Similarity is computed on the behavioural shape, not raw service names. The score panel breaks out lineage, shape, trigger, and temporal contributions — every match is auditable."

---

## 3:45 — 4:30 · Causal Chain & Remediation Transfer

**Show:** **Causal Chain** page for an open incident.

**Walk through one chain on screen:**
> "Deploy at minus thirty minutes. Latency p99 spike at minus ten. Upstream timeout log at minus thirty seconds. Incident signal. Suggested remediation: rollback. Each edge carries an evidence label, a confidence value, and an ordering proof — the engine never says `because of magic`."

**Cut to:** **Remediations** page.

**Say:**
> "Suggestions are ranked by lineage match, shape match, age decay, and a success/failure ledger. Targets are remapped through the alias graph — so a historical rollback on `payments-svc` becomes a rollback on `ledger-v2-r5` if lineage proves equivalence. Operator clicks `worked` or `failed`; that observation feeds back into the ledger and re-weights future suggestions."

---

## 4:30 — 5:00 · Submission Artefacts & Honest Close

**Show:** `SUBMISSION.md` and `docs/p02-writeup.md` side by side.

**Say (slow, deliberate):**
> "What's submitted: the `bench/adapters/memora.py` engine — pure Python stdlib, no network. The `l3_report.json` we just produced. A three-page technical writeup defending memory representation, relationship synthesis, drift handling, latency engineering, and the learning loop. And this 5-minute video.
>
> Headline number: zero point three zero three nine on the L3 automated axes plus 0.20 reserved for panel grading. Latency lands at full credit. Remediation transfer is at 44.8 % accuracy across five action types. Recall and precision are the open work — the alias graph, shape signature, and audit trail are all in place; the next iteration tightens the ranking calibration on cascading renames and the decoy-confidence threshold. The architecture does not change — only the calibration does.
>
> Memora — operational memory for autonomous SRE. Thank you."

**Hold on banner / score frame for two seconds, then cut.**
