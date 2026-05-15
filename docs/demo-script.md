# Memora Demo Script (5 Minutes)

## Goal
Demonstrate to the judges that Memora successfully implements memory-formation during ingestion, relationship synthesis, and resilience against topology drift, while maintaining strict latency bounds.

## Pre-requisites
- Have the repo cloned and terminal open.
- Run `pip install -r requirements.txt`.

---

### Minute 1-2: The Worked Example (Smoke Test)
*Context: We will show the baseline capability to ingest events, build causal edges, and suggest remediations for a basic incident.*

**Action:** 
Run `python bench/worked_example_check.py`

**Talking Points:**
1. Notice how we ingest a stream of historical events first. Memora silently builds `_IncidentProfile` objects and caches their behavioral signatures.
2. We fire the active signal. 
3. Look at the **Causal Chain** output: Memora deterministically linked the upstream `deploy` to the lagging `metric` spike.
4. Look at the **Suggested Remediations**: The system recommends a `rollback` because it matched a historical profile that successfully used a rollback to mitigate a similar deploy-induced failure.

---

### Minute 3: Topology Drift & Rename-Aware Reasoning
*Context: We will prove that Memora's memory survives service renames.*

**Action:**
Show the explanation output from the worked example or run `pytest bench/tests/test_regression.py -k test_topology_rename_boundary -v -s`.

**Talking Points:**
1. A major challenge in AIOps is that a service named `payments-old` yesterday might be `billing-svc` today.
2. Our Alias Graph resolves this in O(1) time. 
3. When `billing-svc` degrades, Memora finds an incident from `payments-old`, matches the signature, and—crucially—translates the historical remediation target *back* to the active `billing-svc` name.
4. "The remediation targets the current infrastructure, not ghosts of the past."

---

### Minute 4-5: Multi-Seed Benchmark Run
*Context: We will run the official judge script to prove stability, recall, precision, and latency across arbitrary random seeds.*

**Action:**
Run `bash bench/run.sh` (which executes `run.py --mode fast --seeds 9999 ...`).

**Talking Points:**
1. The harness generates massive telemetry streams with noise, random topology mutations, and varying incident sequences.
2. Watch the latency printouts: Fast mode evaluates in under 2000ms. This is possible because we moved all heavy lifting (signature generation) to the `ingest()` phase.
3. Review the `report.json` outputs for `recall@5` and `remediation_acc`. 
4. The system successfully outranks failed restarts, decays older remediations, and accurately infers affected services without relying on external LLM egress.
