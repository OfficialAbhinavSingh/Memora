import pytest
from datetime import datetime, timezone, timedelta

from bench.adapters.memora import Engine

def ts_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

@pytest.fixture
def engine():
    eng = Engine()
    yield eng
    eng.close()

def test_training_order(engine):
    """
    Assert that a training incident is fully reconstructed during eval 
    even if reconstruct_context() was never called on it initially.
    """
    t0 = datetime.now(timezone.utc) - timedelta(days=2)
    t1 = datetime.now(timezone.utc)
    
    # Ingest a training incident's events
    engine.ingest([
        {"event_id": "t_d1", "ts": ts_iso(t0 - timedelta(minutes=5)), "kind": "deploy", "service_name": "svc-a", "tenant_id": "1", "environment": "prod"},
        {"event_id": "t_m1", "ts": ts_iso(t0), "kind": "metric", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-train", "attributes": {"name": "error_rate", "value": "5%"}},
        {"event_id": "t_r1", "ts": ts_iso(t0 + timedelta(minutes=5)), "kind": "remediation", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-train", "attributes": {"action": "rollback", "target": "svc-a", "outcome": "resolved"}}
    ])
    
    # Ingest current eval incident events
    engine.ingest([
        {"event_id": "e_d1", "ts": ts_iso(t1 - timedelta(minutes=5)), "kind": "deploy", "service_name": "svc-a", "tenant_id": "1", "environment": "prod"},
        {"event_id": "e_m1", "ts": ts_iso(t1), "kind": "metric", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-eval", "attributes": {"name": "error_rate", "value": "6%"}}
    ])
    
    # Notice we NEVER called reconstruct_context on inc-train
    ctx = engine.reconstruct_context({
        "incident_id": "inc-eval",
        "ts": ts_iso(t1),
        "tenant_id": "1",
        "environment": "prod",
        "service_name": "svc-a",
        "trigger": "alert:svc-a/error_rate>5%"
    }, mode="fast")
    
    assert any(m["past_incident_id"] == "inc-train" for m in ctx["similar_past_incidents"])
    assert any(r["action"] == "rollback" for r in ctx["suggested_remediations"])

def test_topology_rename_boundary(engine):
    """
    Assert that historical events under an old name are matched when querying under the new name.
    """
    t0 = datetime.now(timezone.utc) - timedelta(days=2)
    t1 = datetime.now(timezone.utc)
    
    # Old name events
    engine.ingest([
        {"event_id": "d1", "ts": ts_iso(t0 - timedelta(minutes=5)), "kind": "deploy", "service_name": "payments-old", "tenant_id": "1", "environment": "prod"},
        {"event_id": "m1", "ts": ts_iso(t0), "kind": "metric", "service_name": "payments-old", "tenant_id": "1", "environment": "prod", "incident_id": "inc-1", "attributes": {"name": "latency", "value": "500ms"}},
        {"event_id": "r1", "ts": ts_iso(t0 + timedelta(minutes=5)), "kind": "remediation", "service_name": "payments-old", "tenant_id": "1", "environment": "prod", "incident_id": "inc-1", "attributes": {"action": "scale_up", "target": "payments-old", "outcome": "resolved"}}
    ])
    
    # Topology rename
    engine.ingest([
        {"event_id": "rn1", "ts": ts_iso(t0 + timedelta(days=1)), "kind": "topology", "tenant_id": "1", "environment": "prod", "attributes": {"change": "rename", "from": "payments-old", "to": "billing-svc"}}
    ])
    
    # Current incident on new name
    engine.ingest([
        {"event_id": "m2", "ts": ts_iso(t1), "kind": "metric", "service_name": "billing-svc", "tenant_id": "1", "environment": "prod", "incident_id": "inc-2", "attributes": {"name": "latency", "value": "600ms"}}
    ])
    
    ctx = engine.reconstruct_context({
        "incident_id": "inc-2",
        "ts": ts_iso(t1),
        "tenant_id": "1",
        "environment": "prod",
        "service_name": "billing-svc",
        "trigger": "alert:billing-svc/latency>200ms"
    }, mode="fast")
    
    # Should match the incident from when it was called payments-old
    assert any(m["past_incident_id"] == "inc-1" for m in ctx["similar_past_incidents"])
    # Suggested remediation should point to the NEW name even if it was recorded on the OLD name
    assert any(r["action"] == "scale_up" and r["target"] == "billing-svc" for r in ctx["suggested_remediations"])

def test_remediation_rollback_outranks_restart(engine):
    """
    Assert that a successful rollback outranks a failed restart for the same behavioral signature.
    """
    t0 = datetime.now(timezone.utc) - timedelta(days=2)
    t1 = datetime.now(timezone.utc)
    
    # Train: restart failed, then rollback succeeded
    engine.ingest([
        {"event_id": "d1", "ts": ts_iso(t0 - timedelta(minutes=5)), "kind": "deploy", "service_name": "svc-a", "tenant_id": "1", "environment": "prod"},
        {"event_id": "m1", "ts": ts_iso(t0), "kind": "metric", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-1", "attributes": {"name": "error_rate", "value": "5%"}},
        {"event_id": "r1", "ts": ts_iso(t0 + timedelta(minutes=5)), "kind": "remediation", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-1", "attributes": {"action": "restart", "target": "svc-a", "outcome": "failed"}},
        {"event_id": "r2", "ts": ts_iso(t0 + timedelta(minutes=15)), "kind": "remediation", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-1", "attributes": {"action": "rollback", "target": "svc-a", "outcome": "resolved"}}
    ])
    
    # Eval incident
    engine.ingest([
        {"event_id": "d2", "ts": ts_iso(t1 - timedelta(minutes=5)), "kind": "deploy", "service_name": "svc-a", "tenant_id": "1", "environment": "prod"},
        {"event_id": "m2", "ts": ts_iso(t1), "kind": "metric", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-2", "attributes": {"name": "error_rate", "value": "6%"}}
    ])
    
    ctx = engine.reconstruct_context({
        "incident_id": "inc-2",
        "ts": ts_iso(t1),
        "tenant_id": "1",
        "environment": "prod",
        "service_name": "svc-a",
        "trigger": "alert:svc-a/error_rate>5%"
    }, mode="fast")
    
    rems = ctx["suggested_remediations"]
    assert rems[0]["action"] == "rollback"
    assert "restart" in [r["action"] for r in rems]
    rollback_conf = next(r["confidence"] for r in rems if r["action"] == "rollback")
    restart_conf = next(r["confidence"] for r in rems if r["action"] == "restart")
    assert rollback_conf > restart_conf

def test_decay(engine):
    """
    Assert older successful remediation decays below a recent successful one.
    """
    t_old = datetime.now(timezone.utc) - timedelta(days=200)
    t_new = datetime.now(timezone.utc) - timedelta(days=5)
    t_now = datetime.now(timezone.utc)
    
    # Old incident
    engine.ingest([
        {"event_id": "d1", "ts": ts_iso(t_old - timedelta(minutes=5)), "kind": "deploy", "service_name": "svc-a", "tenant_id": "1", "environment": "prod"},
        {"event_id": "m1", "ts": ts_iso(t_old), "kind": "metric", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-old", "attributes": {"name": "error_rate", "value": "5%"}},
        {"event_id": "r1", "ts": ts_iso(t_old + timedelta(minutes=5)), "kind": "remediation", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-old", "attributes": {"action": "rollback", "target": "svc-a", "outcome": "resolved"}}
    ])
    
    # Newer incident with same shape
    engine.ingest([
        {"event_id": "d2", "ts": ts_iso(t_new - timedelta(minutes=5)), "kind": "deploy", "service_name": "svc-a", "tenant_id": "1", "environment": "prod"},
        {"event_id": "m2", "ts": ts_iso(t_new), "kind": "metric", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-new", "attributes": {"name": "error_rate", "value": "5%"}},
        {"event_id": "r2", "ts": ts_iso(t_new + timedelta(minutes=5)), "kind": "remediation", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-new", "attributes": {"action": "scale_up", "target": "svc-a", "outcome": "resolved"}}
    ])
    
    # Eval incident
    engine.ingest([
        {"event_id": "d3", "ts": ts_iso(t_now - timedelta(minutes=5)), "kind": "deploy", "service_name": "svc-a", "tenant_id": "1", "environment": "prod"},
        {"event_id": "m3", "ts": ts_iso(t_now), "kind": "metric", "service_name": "svc-a", "tenant_id": "1", "environment": "prod", "incident_id": "inc-eval", "attributes": {"name": "error_rate", "value": "6%"}}
    ])
    
    ctx = engine.reconstruct_context({
        "incident_id": "inc-eval",
        "ts": ts_iso(t_now),
        "tenant_id": "1",
        "environment": "prod",
        "service_name": "svc-a",
        "trigger": "alert:svc-a/error_rate>5%"
    }, mode="fast")
    
    rems = ctx["suggested_remediations"]
    assert rems[0]["action"] == "scale_up" # more recent!
    
