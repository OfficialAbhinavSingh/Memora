import pytest
import json
from datetime import datetime, timezone, timedelta
from bench.adapters.memora import Engine

def ts_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Mock generator of heavy events
def generate_events(n_events, base_ts):
    events = []
    for i in range(n_events):
        ts = base_ts + timedelta(seconds=i)
        events.append({
            "event_id": f"e_{i}",
            "ts": ts_iso(ts),
            "kind": "metric",
            "service_name": "svc-a",
            "tenant_id": "1",
            "environment": "prod",
            "attributes": {"name": "latency", "value": f"{100 + i}ms"}
        })
    return events

@pytest.fixture
def engine():
    eng = Engine()
    base = datetime.now(timezone.utc) - timedelta(hours=5)
    # pre-load with 5000 events to simulate some history
    eng.ingest(generate_events(5000, base))
    yield eng, base + timedelta(hours=5)
    eng.close()

def test_latency_fast_mode(benchmark, engine):
    eng, now = engine
    signal = {
        "incident_id": "inc-eval",
        "ts": ts_iso(now),
        "tenant_id": "1",
        "environment": "prod",
        "service_name": "svc-a",
        "trigger": "alert:svc-a/latency>200ms"
    }
    
    def run_fast():
        return eng.reconstruct_context(signal, mode="fast")
        
    result = benchmark(run_fast)
    # The requirement is mean < 2.0s
    assert benchmark.stats.stats.mean < 2.0

def test_latency_deep_mode(benchmark, engine):
    eng, now = engine
    signal = {
        "incident_id": "inc-eval",
        "ts": ts_iso(now),
        "tenant_id": "1",
        "environment": "prod",
        "service_name": "svc-a",
        "trigger": "alert:svc-a/latency>200ms"
    }
    
    def run_deep():
        return eng.reconstruct_context(signal, mode="deep")
        
    result = benchmark(run_deep)
    # The requirement is mean < 6.0s
    assert benchmark.stats.stats.mean < 6.0
