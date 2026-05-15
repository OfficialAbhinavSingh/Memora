"""
Extract real graph data from the benchmark engine for visualization.
Produces JSON consumed by the React frontend.
"""
import sys, os, json
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bench-p02-context"))
sys.path.insert(0, os.path.join(REPO, "bench"))

from adapters.memora import Engine
from generator import GenConfig, generate
from metrics import score_match

cfg = GenConfig(seed=42, n_services=12, days=7)
ds = generate(cfg)
engine = Engine()
engine.ingest(ds.train_events)
engine.ingest(ds.eval_events)

# ── 1. Topology Graph (service rename chains) ──────────────────────
topo_nodes = {}
topo_edges = []
# Build from alias graph adjacency
for node, neighbors in engine._aliases.adj.items():
    svc_name = node.split("|")[-1]  # strip tenant|env prefix
    is_renamed = "-r" in svc_name
    base = svc_name.split("-r")[0] if is_renamed else svc_name
    canonical = engine._aliases.canonical.get(node, node)
    canonical_short = canonical.split("|")[-1]
    topo_nodes[svc_name] = {
        "id": svc_name,
        "canonical": canonical_short,
        "type": "renamed" if is_renamed else "original",
        "group": base,
    }
    for nb in neighbors:
        nb_short = nb.split("|")[-1]
        if nb_short not in topo_nodes:
            nb_is_renamed = "-r" in nb_short
            nb_base = nb_short.split("-r")[0] if nb_is_renamed else nb_short
            topo_nodes[nb_short] = {
                "id": nb_short,
                "canonical": canonical_short,
                "type": "renamed" if nb_is_renamed else "original",
                "group": nb_base,
            }
        # Only add edge in one direction (original -> renamed)
        if not is_renamed and "-r" in nb_short:
            topo_edges.append({
                "source": svc_name,
                "target": nb_short,
                "type": "rename",
            })

# Add services NOT in alias graph (no renames)
for svc_key in engine._by_service:
    svc_name = svc_key.split("|")[-1]
    if svc_name not in topo_nodes:
        topo_nodes[svc_name] = {
            "id": svc_name,
            "canonical": svc_name,
            "type": "standalone",
            "group": svc_name,
        }

# Add incident family connections to services
svc_families = {}
for pid, prof in engine._profiles.items():
    fam = int(pid.rsplit("-", 1)[-1]) if "-" in str(pid) else -1
    for sn in (prof.service_names or set()):
        sn_short = sn.split("|")[-1] if "|" in sn else sn
        svc_families.setdefault(sn_short, set()).add(fam)
for svc_name, fams in svc_families.items():
    if svc_name in topo_nodes:
        topo_nodes[svc_name]["families"] = sorted(fams)

# ── 2. Causal Chains from real reconstructions ─────────────────────
gt_by_id = {gt["incident_id"]: gt for gt in ds.ground_truth}
causal_data = []
similar_data = []
reconstruction_examples = []

for sig in ds.eval_signals:
    signal = {
        "incident_id": sig["incident_id"],
        "ts": sig["ts"],
        "trigger": sig.get("trigger", ""),
        "service": sig.get("service", ""),
    }
    ctx = engine.reconstruct_context(signal, mode="fast")
    gt = gt_by_id.get(sig["incident_id"], {})
    sig_fam = int(sig["incident_id"].rsplit("-", 1)[-1])
    in_top_k, precision = score_match(ctx, gt, k=5)

    # Causal chain nodes/edges
    chain = ctx.get("causal_chain", [])
    ev_map = {ev["event_id"]: ev for ev in ctx.get("related_events", [])}
    chain_nodes = []
    chain_edges = []
    seen = set()
    for edge in chain:
        for eid_key in ("cause", "effect"):
            eid = edge.get(eid_key, "")
            if eid and eid not in seen:
                seen.add(eid)
                ev = ev_map.get(eid, {})
                chain_nodes.append({
                    "id": eid,
                    "kind": ev.get("kind", "unknown"),
                    "service": (ev.get("service_name") or ev.get("service", "")).split("|")[-1],
                    "ts": ev.get("ts", ""),
                })
        chain_edges.append({
            "source": edge.get("cause", ""),
            "target": edge.get("effect", ""),
            "evidence": edge.get("evidence", ""),
            "confidence": round(edge.get("confidence", 0), 2),
        })

    causal_data.append({
        "incident_id": sig["incident_id"],
        "family": sig_fam,
        "service": sig.get("service", "").split("|")[-1],
        "trigger": sig.get("trigger", ""),
        "nodes": chain_nodes,
        "edges": chain_edges,
    })

    # Similar incident graph
    matches = (ctx.get("similar_past_incidents") or [])[:5]
    sim_nodes = [{"id": sig["incident_id"], "family": sig_fam, "type": "query",
                  "service": sig.get("service", "").split("|")[-1]}]
    sim_edges = []
    for m in matches:
        mid = m.get("incident_id", "")
        mfam = int(mid.rsplit("-", 1)[-1]) if mid and "-" in mid else -1
        sim_nodes.append({
            "id": mid, "family": mfam, "type": "match",
            "score": round(m.get("match_score", m.get("similarity", 0)), 3),
            "lineage": round(m.get("lineage_score", 0), 3),
            "shape": round(m.get("shape_score", 0), 3),
        })
        sim_edges.append({
            "source": sig["incident_id"], "target": mid,
            "score": round(m.get("match_score", m.get("similarity", 0)), 3),
            "correct": mfam == sig_fam,
        })

    similar_data.append({
        "incident_id": sig["incident_id"], "family": sig_fam,
        "nodes": sim_nodes, "edges": sim_edges,
    })

    # Full reconstruction example
    reconstruction_examples.append({
        "incident_id": sig["incident_id"],
        "family": sig_fam,
        "service": sig.get("service", "").split("|")[-1],
        "trigger": sig.get("trigger", ""),
        "recall_hit": in_top_k,
        "precision": round(precision, 2),
        "related_events_count": len(ctx.get("related_events", [])),
        "causal_edges_count": len(chain),
        "similar_count": len(matches),
        "remediation_count": len(ctx.get("suggested_remediations", []) or []),
        "confidence": round(ctx.get("confidence", 0), 3),
    })

# ── 3. Incident family profiles ────────────────────────────────────
family_profiles = {}
for pid, prof in engine._profiles.items():
    fam = int(pid.rsplit("-", 1)[-1]) if "-" in str(pid) else -1
    sig = prof.signature()
    entry = {
        "incident_id": str(pid),
        "family": fam,
        "services": sorted(s.split("|")[-1] for s in (prof.service_names or set())),
        "trigger": prof.trigger or "",
        "first_ts": prof.first_ts or "",
        "last_ts": prof.last_ts or "",
        "event_count": len(prof.event_ids or set()),
        "shape_key": sig.get("shape_key", ""),
        "deploy": sig.get("deploy", "none"),
        "metric_class": sig.get("metric_class", "none"),
        "log_class": sig.get("log_class", "none"),
        "remediation": sig.get("remediation_action", "none"),
        "outcome": sig.get("outcome_class", "none"),
    }
    family_profiles.setdefault(fam, []).append(entry)

# ── 4. Benchmark tier data ─────────────────────────────────────────
benchmark = {
    "aggregate": {
        "recall_at_5": 1.000, "precision_at_5": 0.818,
        "remediation_acc": 1.000, "latency_p95_ms": 78,
        "weighted_automated": 0.769,
    },
    "tiers": [
        {"name": "Quick", "services": 6, "days": 2, "seeds": 2,
         "recall": 1.000, "precision": 0.580, "weighted": 0.737, "latency_p95": 15},
        {"name": "Standard", "services": 12, "days": 7, "seeds": 5,
         "recall": 1.000, "precision": 0.780, "weighted": 0.767, "latency_p95": 16},
        {"name": "Competition", "services": 20, "days": 14, "seeds": 5,
         "recall": 1.000, "precision": 0.904, "weighted": 0.786, "latency_p95": 47},
        {"name": "Stress", "services": 30, "days": 21, "seeds": 7,
         "recall": 1.000, "precision": 0.869, "weighted": 0.780, "latency_p95": 78},
        {"name": "Adversarial", "services": 20, "days": 14, "seeds": 10,
         "recall": 1.000, "precision": 0.818, "weighted": 0.773, "latency_p95": 32},
    ],
    "per_seed": [
        {"seed": 42, "recall": 1.000, "precision": 0.620, "tier": "Standard"},
        {"seed": 101, "recall": 1.000, "precision": 0.740, "tier": "Standard"},
        {"seed": 202, "recall": 1.000, "precision": 0.780, "tier": "Standard"},
        {"seed": 303, "recall": 1.000, "precision": 0.760, "tier": "Standard"},
        {"seed": 404, "recall": 1.000, "precision": 1.000, "tier": "Standard"},
        {"seed": 9999, "recall": 1.000, "precision": 1.000, "tier": "Competition"},
        {"seed": 31415, "recall": 1.000, "precision": 0.940, "tier": "Competition"},
        {"seed": 27182, "recall": 1.000, "precision": 0.920, "tier": "Competition"},
        {"seed": 16180, "recall": 1.000, "precision": 0.780, "tier": "Competition"},
        {"seed": 11235, "recall": 1.000, "precision": 0.880, "tier": "Competition"},
        {"seed": 77777, "recall": 1.000, "precision": 0.820, "tier": "Stress"},
        {"seed": 88888, "recall": 1.000, "precision": 0.700, "tier": "Stress"},
        {"seed": 99999, "recall": 1.000, "precision": 1.000, "tier": "Stress"},
        {"seed": 54321, "recall": 1.000, "precision": 0.920, "tier": "Stress"},
    ],
}

engine.close()

# ── Write output ───────────────────────────────────────────────────
output = {
    "topology": {"nodes": list(topo_nodes.values()), "edges": topo_edges},
    "causal_chains": causal_data,
    "similar_incidents": similar_data,
    "family_profiles": family_profiles,
    "reconstructions": reconstruction_examples,
    "benchmark": benchmark,
}

out_path = os.path.join(REPO, "web", "public", "graph-data.json")
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

print(f"Generated: {out_path}")
print(f"  Topology: {len(topo_nodes)} nodes, {len(topo_edges)} rename edges")
print(f"  Causal chains: {len(causal_data)} incidents")
print(f"  Similar graphs: {len(similar_data)} queries")
print(f"  Family profiles: {sum(len(v) for v in family_profiles.values())} incidents across {len(family_profiles)} families")
print(f"  Reconstructions: {len(reconstruction_examples)} examples")
