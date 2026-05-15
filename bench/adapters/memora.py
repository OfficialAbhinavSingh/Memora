from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Iterable

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_ts(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _iso(value):
    return _parse_ts(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_id(event):
    raw = "|".join([
        str(event.get("tenant_id", "default")),
        str(event.get("environment", "prod")),
        str(event.get("kind", "")),
        str(event.get("service_name", event.get("service", ""))),
        str(event.get("ts", "")),
        json.dumps(event, sort_keys=True, default=str),
    ])
    return hashlib.sha1(raw.encode()).hexdigest()


def _confidence(v):
    return round(max(0.0, min(1.0, v)), 2)


def _incident_family(incident_id: str):
    try:
        return int(str(incident_id).rsplit("-", 1)[-1])
    except (TypeError, ValueError, IndexError):
        return str(incident_id)


def _jaccard(left, right) -> float:
    a, b = set(left or []), set(right or [])
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def _primary(values, default: str = "none") -> str:
    vals = sorted(v for v in (values or []) if v)
    return vals[0] if vals else default


# ---------------------------------------------------------------------------
# Service inference from trigger strings
# e.g. "alert:checkout-api/error-rate>5%"  ->  "checkout-api"
#      "alert:payments-svc/latency_p99>500ms" -> "payments-svc"
# ---------------------------------------------------------------------------

_TRIGGER_SVC_RE = re.compile(
    r"(?:alert:|pagerduty:|oncall:|slo:)?([a-z0-9][a-z0-9_-]{1,48}(?:-svc|-api|-service|-worker|-job|-db|-cache))"
    r"(?:/|#|:|\s)",
    re.IGNORECASE,
)

def _infer_service_from_trigger(trigger: str) -> str:
    """Parse first service-like token from a trigger/alert string."""
    if not trigger:
        return ""
    m = _TRIGGER_SVC_RE.search(trigger)
    return m.group(1).lower() if m else ""


def _event_services(event: dict) -> set[str]:
    services = set()
    if event.get("service_name"):
        services.add(str(event["service_name"]).lower())
    for entity in event.get("entities", []):
        services.add(str(entity).lower())
    for span in event.get("attributes", {}).get("spans", []) or []:
        if span.get("svc"):
            services.add(str(span["svc"]).lower())
    return services


def _slowest_trace_service(event: dict) -> str:
    spans = event.get("attributes", {}).get("spans", []) or []
    best = ("", -1.0)
    for span in spans:
        try:
            dur = float(span.get("dur_ms", 0))
        except (TypeError, ValueError):
            dur = 0.0
        svc = str(span.get("svc", "")).lower()
        if svc and dur > best[1]:
            best = (svc, dur)
    return best[0]


def _trace_roles(event: dict) -> set[str]:
    spans = event.get("attributes", {}).get("spans", []) or []
    roles = set()
    if len(spans) >= 2:
        roles.add("caller-callee")
        slow = _slowest_trace_service(event)
        if slow:
            roles.add("slow-callee")
    return roles


def _infer_service_from_events(events: list, window_ts: datetime, window: timedelta, trigger: str = "") -> str:
    """Pick the most likely failing service from nearby behavior."""
    scores: Counter[str] = Counter()
    lo, hi = window_ts - window, window_ts + window
    alerting = _infer_service_from_trigger(trigger)
    for e in events:
        if not (lo <= _parse_ts(e["ts"]) <= hi):
            continue
        kind = e.get("kind")
        svc = str(e.get("service_name", "")).lower()
        if kind == "metric":
            if svc:
                scores[svc] += 5 if _metric_is_anomaly(e) else 1
        elif kind == "trace":
            slow = _slowest_trace_service(e)
            if slow:
                scores[slow] += 5
            if svc:
                scores[svc] += 1
        elif kind == "log":
            attrs = e.get("attributes", {})
            msg = str(attrs.get("msg", attrs.get("message", ""))).lower()
            mentioned = [s for s in _event_services(e) if s != svc]
            for target in mentioned:
                scores[target] += 4 if _log_is_failure(e) else 1
            if svc:
                scores[svc] += 2 if _log_is_failure(e) and svc != alerting else 1
            for token in re.findall(r"[a-z0-9][a-z0-9_-]*(?:-svc|-api|-service|-worker|-job|-db|-cache)", msg):
                if token != alerting:
                    scores[token] += 4
        elif svc:
            scores[svc] += 1
    if not scores:
        return alerting
    return scores.most_common(1)[0][0]


def _metric_is_anomaly(event: dict) -> bool:
    attrs = event.get("attributes", {})
    name = str(attrs.get("name", "")).lower()
    try:
        value = float(str(attrs.get("value", 0)).rstrip("%"))
    except (TypeError, ValueError):
        value = 0.0
    if "error" in name or "failure" in name:
        return value > 1.0
    if any(token in name for token in ("latency", "p99", "p95", "duration", "ms")):
        return value > 200
    return value >= 1000


def _log_is_failure(event: dict) -> bool:
    attrs = event.get("attributes", {})
    msg = str(attrs.get("msg", attrs.get("message", ""))).lower()
    level = str(attrs.get("level", "")).lower()
    return level in ("error", "fatal", "critical") or any(
        token in msg for token in ("timeout", "refused", "error", "exception", "failed", "5xx", "500")
    )


# ---------------------------------------------------------------------------
# Alias graph (union-find with BFS connected-component resolution)
# ---------------------------------------------------------------------------

class _AliasGraph:
    def __init__(self):
        self.canonical: dict[str, str] = {}
        self.adj: dict[str, set] = {}

    def upsert(self, tenant, env, src, tgt):
        if not src or not tgt:
            return
        a, b = self._key(tenant, env, src), self._key(tenant, env, tgt)
        for k in self._connected(a) | self._connected(b):
            self.canonical[k] = b
        self.adj.setdefault(a, set()).add(b)
        self.adj.setdefault(b, set()).add(a)

    def resolve(self, tenant, env, service):
        if not service:
            return ""
        k = self._key(tenant, env, service)
        return self.canonical.get(k, k)

    def aliases(self, tenant, env, service):
        if not service:
            return []
        start = self._key(tenant, env, service)
        prefix = f"{tenant}|{env}|"
        return sorted(
            k[len(prefix):] if k.startswith(prefix) else k
            for k in self._connected(start)
        )

    def _connected(self, start):
        seen, q = {start}, deque([start])
        while q:
            cur = q.popleft()
            for nxt in self.adj.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        return seen

    @staticmethod
    def _key(tenant, env, service):
        return f"{tenant}|{env}|{str(service).lower()}"


# ---------------------------------------------------------------------------
# Incident Profile — formed incrementally during ingest
# ---------------------------------------------------------------------------

class _IncidentProfile:
    """Accumulates evidence for one incident during ingest."""

    def __init__(self, incident_id, tenant_id, environment):
        self.incident_id = incident_id
        self.tenant_id = tenant_id
        self.environment = environment
        self.events: list[dict] = []
        self.event_ids: set[str] = set()
        self.remediations: list[dict] = []
        self.affected_canonical: set[str] = set()
        self.service_names: set[str] = set()
        self.trigger: str = ""
        self.first_ts: str = ""
        self.last_ts: str = ""
        self.resolved: bool = False
        self._sig: dict = {}

    def add(self, event: dict) -> None:
        event_id = event.get("event_id", "")
        if event_id and event_id in self.event_ids:
            return
        if event_id:
            self.event_ids.add(event_id)
        self.events.append(event)
        if c := event.get("canonical_service_id"):
            self.affected_canonical.add(c)
        if svc := event.get("service_name"):
            self.service_names.add(str(svc).lower())
        for entity in event.get("entities", []):
            self.service_names.add(str(entity).lower())
        ts = event.get("ts", "")
        if not self.first_ts or ts < self.first_ts:
            self.first_ts = ts
        if not self.last_ts or ts > self.last_ts:
            self.last_ts = ts
        if event["kind"] == "remediation":
            self.remediations.append(event)
            outcome = event.get("attributes", {}).get("outcome", "").lower()
            if outcome in ("resolved", "success", "worked"):
                self.resolved = True
        self._sig = {}  # invalidate

    def signature(self) -> dict:
        """Compute topology-independent behavioral signature (cached)."""
        if self._sig:
            return self._sig
        evs = self.events
        kinds = {e["kind"] for e in evs}
        deploy_ts = next((e["ts"] for e in evs if e["kind"] == "deploy"), None)
        anomaly_ts = next(
            (e["ts"] for e in evs
             if e["kind"] in ("metric", "trace", "log") and (not deploy_ts or e["ts"] > deploy_ts)),
            None,
        )
        delay = "no-deploy"
        if deploy_ts and anomaly_ts:
            try:
                s = (_parse_ts(anomaly_ts) - _parse_ts(deploy_ts)).total_seconds()
                delay = "<5m" if s < 300 else "5-15m" if s < 900 else "15-30m" if s < 1800 else ">30m"
            except Exception:
                delay = "unknown"
        metric_cls, log_cls, trace_cls = set(), set(), set()
        for e in evs:
            a = e.get("attributes", {})
            name = str(a.get("name", "")).lower()
            msg = str(a.get("msg", a.get("message", ""))).lower()
            if any(k in name for k in ("latency", "p99", "p95", "duration", "ms")):
                metric_cls.add("latency")
            if any(k in name for k in ("error", "5xx", "4xx", "rate", "failure")):
                metric_cls.add("error")
            if any(k in name for k in ("cpu", "memory", "saturation", "queue", "util")):
                metric_cls.add("saturation")
            if any(k in msg for k in ("timeout", "timed out", "deadline")):
                log_cls.add("timeout")
            if any(k in msg for k in ("refused", "econnrefused", "connection")):
                log_cls.add("connection")
            if any(k in msg for k in ("500", "502", "503", "504", "5xx")):
                log_cls.add("5xx")
            if e.get("kind") == "metric" and _metric_is_anomaly(e):
                metric_cls.add("anomaly")
            if e.get("kind") == "log" and _log_is_failure(e):
                log_cls.add("failure")
            if e.get("kind") == "trace":
                trace_cls.update(_trace_roles(e))
        remediation_types = sorted({
            str(r.get("attributes", {}).get("action", "")).lower()
            for r in self.remediations
        })
        outcome_class = "resolved" if self.resolved else "failed" if any(
            str(r.get("attributes", {}).get("outcome", "")).lower() == "failed"
            for r in self.remediations
        ) else "unknown"
        shape_key = "|".join([
            "deploy" if "deploy" in kinds else "no-deploy",
            delay,
            _primary(metric_cls),
            _primary(log_cls),
            _primary(trace_cls),
            _primary(remediation_types),
            outcome_class,
        ])
        self._sig = {
            "has_deploy": "deploy" in kinds,
            "has_metric": "metric" in kinds,
            "has_trace": "trace" in kinds,
            "has_log": "log" in kinds,
            "has_remediation": bool(self.remediations),
            "delay_bucket": delay,
            "metric_class": sorted(metric_cls),
            "log_class": sorted(log_cls),
            "trace_class": sorted(trace_cls),
            "remediation_types": remediation_types,
            "outcome_class": outcome_class,
            "shape_key": shape_key,
            "resolved": self.resolved,
        }
        return self._sig

    def sig_similarity_details(self, other: "_IncidentProfile") -> tuple[float, dict]:
        a, b = self.signature(), other.signature()
        score = weight = 0.0
        parts = {}

        def bm(k, w):
            nonlocal score, weight
            weight += w
            hit = a.get(k) == b.get(k)
            parts[k] = 1.0 if hit else 0.0
            if a.get(k) == b.get(k):
                score += w

        def sm(k, w):
            nonlocal score, weight
            weight += w
            sa, sb = set(a.get(k, [])), set(b.get(k, []))
            similarity = len(sa & sb) / max(len(sa | sb), 1) if (sa or sb) else 1.0
            parts[k] = round(similarity, 3)
            score += w * similarity

        bm("has_deploy", 1.5)
        bm("delay_bucket", 2.0)
        sm("metric_class", 2.5)
        sm("log_class", 2.0)
        sm("trace_class", 1.5)
        bm("has_remediation", 1.0)
        sm("remediation_types", 1.5)
        bm("resolved", 0.5)
        overall = score / weight if weight else 0.0
        return overall, {
            "overall": round(overall, 3),
            "current_signature": a,
            "historical_signature": b,
            "components": parts,
        }

    def sig_similarity(self, other: "_IncidentProfile") -> float:
        score, _ = self.sig_similarity_details(other)
        return score

# ---------------------------------------------------------------------------
# Engine — public API expected by Anvil benchmark harness
# ---------------------------------------------------------------------------

class Engine:
    def __init__(self):
        self._events: list[dict] = []
        self._aliases = _AliasGraph()
        # indexes
        self._by_service: dict[str, list[dict]] = defaultdict(list)   # canonical -> events
        self._by_incident: dict[str, list[dict]] = defaultdict(list)  # incident_id -> events
        self._profiles: dict[str, _IncidentProfile] = {}              # incident_id -> profile
        self._feedback: list[dict] = []

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def ingest(self, events: Iterable[dict]) -> None:
        batch_signals = []
        batch_remediations = []
        for raw in events:
            ev = self._normalize(raw)
            self._resolve_canonical(ev)
            self._events.append(ev)
            # update indexes
            if c := ev.get("canonical_service_id"):
                self._by_service[c].append(ev)
            if iid := ev.get("incident_id"):
                self._by_incident[iid].append(ev)
                self._update_profile(iid, ev)
            if ev["kind"] == "incident_signal":
                batch_signals.append(ev)
                self._seed_profile_from_signal(ev)
            if ev["kind"] == "remediation":
                batch_remediations.append(ev)
                self._feedback.append({
                    "incident_id": ev.get("incident_id", ""),
                    "tenant_id": ev["tenant_id"],
                    "environment": ev["environment"],
                    "action": ev["attributes"].get("action", ""),
                    "target": ev["attributes"].get("target", ev.get("service_name", "")),
                    "outcome": ev["attributes"].get("outcome", ""),
                    "observed_at": ev["ts"],
                    "service_name": ev.get("service_name", ""),
                    "canonical_service_id": ev.get("canonical_service_id", ""),
                })
                self._attach_remediation_to_nearby_profiles(ev)
        # sort just new batch's range (already sorted prefix)
        self._events.sort(key=lambda e: (e["ts"], e["event_id"]))
        for signal in batch_signals:
            self._seed_profile_from_signal(signal)
        for remediation in batch_remediations:
            self._attach_remediation_to_nearby_profiles(remediation)

    def ingest_jsonl(self, text: str) -> None:
        evts = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                evts.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL line: {line!r}") from exc
        self.ingest(evts)

    def ingest_file(self, path: str) -> None:
        import pathlib
        self.ingest_jsonl(pathlib.Path(path).read_text(encoding="utf-8"))

    def close(self):
        return None

    # ------------------------------------------------------------------
    # reconstruct_context
    # ------------------------------------------------------------------

    def reconstruct_context(self, signal: dict, mode: str = "fast") -> dict:
        sig = self._normalize_signal(signal)
        window = timedelta(minutes=30 if mode == "fast" else 240)
        sig_ts = _parse_ts(sig["ts"])
        lo, hi = sig_ts - window, sig_ts + timedelta(minutes=15)

        # --- service resolution: try field, then trigger, then events ---
        svc = sig.get("service_name", "")
        explicit_svc = bool(svc)
        if not svc:
            svc = _infer_service_from_trigger(sig.get("trigger", ""))
        if not svc or svc == _infer_service_from_trigger(sig.get("trigger", "")):
            inferred = _infer_service_from_events(self._events, sig_ts, window, sig.get("trigger", ""))
            if inferred:
                svc = inferred
        if svc:
            sig["service_name"] = svc
            sig["canonical_service_id"] = self._aliases.resolve(
                sig["tenant_id"], sig["environment"], svc
            )
            if not explicit_svc and "|" in sig["canonical_service_id"]:
                sig["service_name"] = sig["canonical_service_id"].split("|", 2)[-1]
                svc = sig["service_name"]

        canonical = sig.get("canonical_service_id", "")
        all_aliases = set(self._aliases.aliases(sig["tenant_id"], sig["environment"], svc))
        all_aliases.add(svc)
        if canonical:
            all_aliases.add(canonical)

        candidates = self._candidate_events(
            sig["tenant_id"], sig["environment"], lo, hi, all_aliases, canonical, sig["incident_id"]
        )

        related_limit = 10 if mode == "fast" else 25
        causal_limit = 8 if mode == "fast" else 20
        related = self._rank_related(sig, candidates, sig_ts, limit=related_limit)
        causal = self._causal_edges(related, limit=causal_limit)
        similar = self._similar(sig, related)
        remediations = self._remediations(sig, similar, all_aliases, sig_ts)
        confidence = _confidence(
            0.10
            + min(0.30, len(related) * 0.04)
            + min(0.25, len(causal) * 0.09)
            + min(0.25, len(similar) * 0.07)
            + min(0.10, len(remediations) * 0.04)
        )
        ctx = {
            "related_events": related,
            "causal_chain": causal,
            "similar_past_incidents": similar,
            "suggested_remediations": remediations,
            "confidence": confidence,
            "explain": self._explain(sig, related, causal, similar, remediations),
        }
        # store memory for future similarity lookups
        iid = sig["incident_id"] or _stable_id(sig)
        if iid not in self._profiles:
            self._profiles[iid] = _IncidentProfile(iid, sig["tenant_id"], sig["environment"])
        # always update trigger (may have been empty during ingest)
        if sig.get("trigger") and not self._profiles[iid].trigger:
            self._profiles[iid].trigger = sig["trigger"]
        for e in related:
            self._profiles[iid].add(e)
        self._profiles[iid].signature()  # pre-compute
        return ctx

    # ------------------------------------------------------------------
    # Internal: normalize
    # ------------------------------------------------------------------

    def _normalize(self, raw: dict) -> dict:
        attrs = dict(raw.get("attributes") or {})
        kind = raw.get("kind", "")
        svc = raw.get("service_name") or raw.get("service") or raw.get("svc") or ""
        if kind == "deploy":
            attrs.setdefault("version", raw.get("version", ""))
        elif kind == "log":
            attrs.setdefault("level", raw.get("level", ""))
            attrs.setdefault("msg", raw.get("msg", ""))
        elif kind == "metric":
            attrs.setdefault("name", raw.get("name", ""))
            attrs.setdefault("value", raw.get("value", 0))
        elif kind == "trace":
            attrs.setdefault("spans", raw.get("spans", []))
            if not svc and raw.get("spans"):
                svc = raw["spans"][0].get("svc", "")
        elif kind == "topology":
            attrs.setdefault("change", raw.get("change", ""))
            attrs.setdefault("from", raw.get("from", ""))
            attrs.setdefault("to", raw.get("to", ""))
            svc = svc or attrs.get("to", "")
        elif kind == "remediation":
            attrs.setdefault("action", raw.get("action", ""))
            attrs.setdefault("target", raw.get("target", svc))
            attrs.setdefault("version", raw.get("version", ""))
            attrs.setdefault("outcome", raw.get("outcome", ""))
            svc = svc or attrs.get("target", "")
        elif kind == "incident_signal":
            attrs.setdefault("trigger", raw.get("trigger", ""))
            attrs.setdefault("service", raw.get("service", raw.get("service_name", "")))
            svc = svc or attrs.get("service", "")
        # extract entity mentions (service names embedded in attr blobs)
        entities = set(raw.get("entities") or [])
        for span in attrs.get("spans", []) or []:
            if span.get("svc"):
                entities.add(span["svc"])
        blob = json.dumps(attrs, default=str)
        for tok in re.findall(r"[a-z0-9][a-z0-9_-]*(?:-svc|-api|-service|-worker|-job)", blob, re.IGNORECASE):
            entities.add(tok.lower())
        tenant = raw.get("tenant_id", "default")
        env = raw.get("environment", "prod")
        return {
            "event_id": raw.get("event_id") or _stable_id(raw),
            "ts": _iso(raw.get("ts")),
            "kind": kind,
            "tenant_id": tenant,
            "environment": env,
            "service_name": svc,
            "canonical_service_id": raw.get("canonical_service_id", ""),
            "incident_id": raw.get("incident_id") or attrs.get("incident_id", ""),
            "trace_id": raw.get("trace_id", ""),
            "entities": sorted(entities),
            "attributes": attrs,
        }

    def _resolve_canonical(self, event: dict) -> None:
        t, e = event["tenant_id"], event["environment"]
        kind = event["kind"]
        attrs = event["attributes"]
        if kind == "topology" and attrs.get("change") == "rename":
            self._aliases.upsert(t, e, attrs.get("from", ""), attrs.get("to", ""))
            event["canonical_service_id"] = self._aliases.resolve(t, e, attrs.get("to", ""))
        elif event["service_name"]:
            event["canonical_service_id"] = self._aliases.resolve(t, e, event["service_name"])

    def _normalize_signal(self, signal: dict) -> dict:
        attrs = signal.get("attributes") or {}
        svc = signal.get("service_name") or signal.get("service") or attrs.get("service") or ""
        tenant = signal.get("tenant_id", "default")
        env = signal.get("environment", "prod")
        canonical = signal.get("canonical_service_id") or self._aliases.resolve(tenant, env, svc)
        return {
            "incident_id": signal.get("incident_id", ""),
            "ts": _iso(signal.get("ts")),
            "tenant_id": tenant,
            "environment": env,
            "service_name": svc,
            "canonical_service_id": canonical,
            "trigger": signal.get("trigger", ""),
            "attributes": attrs,
        }

    def _update_profile(self, incident_id: str, event: dict) -> None:
        if incident_id not in self._profiles:
            self._profiles[incident_id] = _IncidentProfile(
                incident_id, event["tenant_id"], event["environment"]
            )
        profile = self._profiles[incident_id]
        if event["kind"] == "incident_signal":
            trigger = event.get("attributes", {}).get("trigger", "")
            if trigger:
                profile.trigger = trigger
        profile.add(event)

    def _seed_profile_from_signal(self, signal_event: dict) -> None:
        incident_id = signal_event.get("incident_id")
        if not incident_id:
            return
        profile = self._profiles[incident_id]
        attrs = signal_event.get("attributes", {})
        trigger = str(attrs.get("trigger", ""))
        if trigger:
            profile.trigger = trigger
        sig_ts = _parse_ts(signal_event["ts"])
        service = signal_event.get("service_name") or _infer_service_from_trigger(trigger)
        if not service:
            service = _infer_service_from_events(self._events, sig_ts, timedelta(minutes=30), trigger)
        canonical = self._aliases.resolve(signal_event["tenant_id"], signal_event["environment"], service)
        aliases = set(self._aliases.aliases(signal_event["tenant_id"], signal_event["environment"], service))
        if service:
            aliases.add(service)
        if canonical:
            aliases.add(canonical)
            profile.affected_canonical.add(canonical)

        candidates = self._candidate_events(
            signal_event["tenant_id"],
            signal_event["environment"],
            sig_ts - timedelta(minutes=45),
            sig_ts + timedelta(minutes=10),
            aliases,
            canonical,
            incident_id,
        )
        for event in self._rank_related({
            "incident_id": incident_id,
            "ts": signal_event["ts"],
            "tenant_id": signal_event["tenant_id"],
            "environment": signal_event["environment"],
            "service_name": service,
            "canonical_service_id": canonical,
            "trigger": trigger,
            "attributes": attrs,
        }, candidates, sig_ts, limit=20):
            profile.add(event)
        profile.signature()

    def _attach_remediation_to_nearby_profiles(self, remediation: dict) -> None:
        incident_id = remediation.get("incident_id")
        if incident_id and incident_id in self._profiles:
            self._profiles[incident_id].add(remediation)
            return
        rem_ts = _parse_ts(remediation["ts"])
        target = str(remediation.get("service_name") or remediation.get("attributes", {}).get("target", "")).lower()
        for profile in self._profiles.values():
            if profile.tenant_id != remediation["tenant_id"] or profile.environment != remediation["environment"]:
                continue
            if not profile.last_ts:
                continue
            if not (timedelta(0) <= rem_ts - _parse_ts(profile.last_ts) <= timedelta(hours=2)):
                continue
            if target and target not in profile.service_names:
                aliases = set()
                for service in profile.service_names:
                    aliases.update(self._aliases.aliases(profile.tenant_id, profile.environment, service))
                if target not in {a.lower() for a in aliases}:
                    continue
            profile.add(remediation)

    def _candidate_events(self, tenant: str, env: str, lo: datetime, hi: datetime, aliases: set, canonical: str, incident_id: str = "") -> list:
        return [
            e for e in self._events
            if e["tenant_id"] == tenant
            and e["environment"] == env
            and lo <= _parse_ts(e["ts"]) <= hi
            and (
                not aliases
                or self._svc_match(e, aliases, canonical)
                or (incident_id and e.get("incident_id") == incident_id)
            )
        ]

    # ------------------------------------------------------------------
    # Internal: matching helpers
    # ------------------------------------------------------------------

    def _svc_match(self, event: dict, aliases: set, canonical: str) -> bool:
        if not aliases:
            return True
        esvc = event.get("service_name", "").lower()
        ecan = event.get("canonical_service_id", "")
        if ecan and (ecan == canonical or ecan in aliases):
            return True
        if esvc and esvc in {a.lower() for a in aliases}:
            return True
        for ent in event.get("entities", []):
            if ent.lower() in {a.lower() for a in aliases}:
                return True
        return False

    # ------------------------------------------------------------------
    # Internal: rank related events
    # ------------------------------------------------------------------

    def _rank_related(self, sig: dict, candidates: list, sig_ts: datetime, limit: int = 10) -> list:
        canonical = sig.get("canonical_service_id", "")
        svc_lower = (sig.get("service_name") or "").lower()
        incident_id = sig.get("incident_id", "")

        # ---- Pass 1: gate on primary signal -----------------------------------
        # An event must match on canonical service, service name, OR incident_id.
        # Time proximity and kind bonuses are secondary — they cannot get an event
        # past the gate on their own (that was the precision leak).
        scored = []
        primary_trace_ids: set[str] = set()

        tenant = sig.get("tenant_id", "default")
        env = sig.get("environment", "prod")

        for ev in candidates:
            ev_can = ev.get("canonical_service_id", "")
            ev_svc = (ev.get("service_name") or "").lower()
            ev_iid = ev.get("incident_id", "")
            ev_tid = ev.get("trace_id", "")

            # Resolve stored canonical through LIVE alias graph (handles pre-rename events)
            live_ev_can = self._aliases.canonical.get(ev_can, ev_can) if ev_can else ""
            live_svc_can = self._aliases.resolve(tenant, env, ev_svc) if ev_svc else ""

            s = 0.0
            primary = False

            if canonical and (ev_can == canonical or live_ev_can == canonical or live_svc_can == canonical):
                s += 0.40
                primary = True
            if svc_lower and ev_svc == svc_lower:
                s += 0.20
                primary = True
            if incident_id and ev_iid == incident_id:
                s += 0.30
                primary = True

            if not primary:
                continue  # drop time-coincident noise from other services

            # Secondary scoring (kind + temporal proximity only)
            s += {"deploy": 0.18, "metric": 0.16, "log": 0.14,
                  "trace": 0.14, "remediation": 0.12}.get(ev["kind"], 0)
            delta = abs((sig_ts - _parse_ts(ev["ts"])).total_seconds() / 60)
            s += max(0.0, 0.15 - delta / 200)  # smaller temporal bonus

            if s >= 0.30:  # raised from 0.15
                scored.append((s, delta, ev))
                if ev_tid:
                    primary_trace_ids.add(ev_tid)

        scored.sort(key=lambda x: (-x[0], x[1], x[2]["event_id"]))
        seen: set[str] = set()
        out: list[dict] = []
        for _, _, ev in scored:
            if ev["event_id"] not in seen:
                seen.add(ev["event_id"])
                out.append(ev)
                if len(out) == limit:
                    break

        # ---- Pass 2: trace-ID linking ----------------------------------------
        # Events sharing a trace_id with a primary event are causally linked;
        # include them even if they belong to a different service (e.g. caller).
        if primary_trace_ids and len(out) < limit:
            for ev in candidates:
                if len(out) >= limit:
                    break
                if ev["event_id"] in seen:
                    continue
                if ev.get("trace_id") and ev["trace_id"] in primary_trace_ids:
                    seen.add(ev["event_id"])
                    out.append(ev)

        return sorted(out, key=lambda e: (e["ts"], e["event_id"]))

    # ------------------------------------------------------------------
    # Internal: causal edges (more types than before)
    # ------------------------------------------------------------------

    def _causal_edges(self, events: list, limit: int = 8) -> list:
        deploys   = [e for e in events if e["kind"] == "deploy"]
        metrics   = [e for e in events if e["kind"] == "metric" and self._is_anomaly_metric(e)]
        logs      = [e for e in events if e["kind"] == "log" and self._is_failure_log(e)]
        traces    = [e for e in events if e["kind"] == "trace"]
        remeds    = [e for e in events if e["kind"] == "remediation"]
        edges = []

        def _ts(e): return _parse_ts(e["ts"])
        def _before(a, b, max_min=60): return 0 < (_ts(b) - _ts(a)).total_seconds() <= max_min * 60
        def _ordering_proof(a, b):
            delta = int((_ts(b) - _ts(a)).total_seconds())
            return f"{a['ts']} precedes {b['ts']} by {delta}s"

        def _edge(cause, effect, label, confidence, ordering_proof=None):
            cause_id = cause["event_id"] if isinstance(cause, dict) else str(cause)
            effect_id = effect["event_id"] if isinstance(effect, dict) else str(effect)
            proof = ordering_proof
            if proof is None and isinstance(cause, dict) and isinstance(effect, dict):
                proof = _ordering_proof(cause, effect)
            return {
                "cause_id": cause_id,
                "effect_id": effect_id,
                "cause_event_id": cause_id,
                "effect_event_id": effect_id,
                "evidence": [label],
                "evidence_label": label,
                "confidence": confidence,
                "ordering_proof": proof or "ordering inferred from event provenance",
            }

        # deploy → metric spike
        for d in deploys:
            for m in metrics:
                if _before(d, m, 60):
                    edges.append(_edge(d, m, "deploy_precedes_metric_spike", 0.82))
        # deploy → log failure
        for d in deploys:
            for l in logs:
                if _before(d, l, 60):
                    edges.append(_edge(d, l, "deploy_precedes_log_failure", 0.75))
        # metric spike → upstream log failure
        for m in metrics:
            for l in logs:
                if _before(m, l, 30):
                    edges.append(_edge(m, l, "metric_spike_precedes_failure", 0.68))
        # trace caller → callee latency
        for t in traces:
            spans = t.get("attributes", {}).get("spans", []) or []
            if len(spans) >= 2:
                for i in range(len(spans) - 1):
                    caller_svc = spans[i].get("svc", "")
                    callee_svc = spans[i + 1].get("svc", "")
                    if caller_svc != callee_svc:
                        edges.append(_edge(
                            t,
                            t["event_id"] + f"_span{i}",
                            f"trace_caller_{caller_svc}_callee_{callee_svc}",
                            0.65,
                            "single trace preserves caller/callee span order",
                        ))
        # log failure → remediation
        for l in logs:
            for r in remeds:
                if _before(l, r, 120):
                    edges.append(_edge(l, r, "failure_log_triggers_remediation", 0.70))
        # deduplicate by (cause, effect), keep highest confidence
        best: dict[tuple, dict] = {}
        for edge in edges:
            key = (edge["cause_id"], edge["effect_id"])
            if key not in best or edge["confidence"] > best[key]["confidence"]:
                best[key] = edge
        return sorted(best.values(), key=lambda e: (-e["confidence"], e["cause_id"]))[:limit]

    # ------------------------------------------------------------------
    # Internal: similar incidents
    # ------------------------------------------------------------------

    def _similar(self, sig: dict, related: list) -> list:
        # Build a temporary profile for the current signal
        tmp = _IncidentProfile(sig["incident_id"] or "__current__", sig["tenant_id"], sig["environment"])
        tmp.trigger = sig.get("trigger", "")
        for ev in related:
            tmp.add(ev)
        tmp.signature()

        canonical = sig.get("canonical_service_id", "")
        trigger = sig.get("trigger", "").lower()
        trigger_svc = _infer_service_from_trigger(trigger)
        matches = []

        for iid, profile in self._profiles.items():
            if iid == sig.get("incident_id"):
                continue
            if profile.tenant_id != sig["tenant_id"] or profile.environment != sig["environment"]:
                continue

            contributors = {}
            live_cans = set()
            lineage_score = 0.0
            # canonical service match — resolve stored canonicals through the
            # CURRENT alias graph so renamed services (payments-svc -> billing-svc)
            # still match historical profiles built pre-rename.
            if canonical:
                live_cans = {
                    self._aliases.canonical.get(c, c)
                    for c in profile.affected_canonical
                }
                if canonical in live_cans:
                    lineage_score = 1.0
                else:
                    current_aliases = {
                        a.lower()
                        for a in self._aliases.aliases(sig["tenant_id"], sig["environment"], sig.get("service_name", ""))
                    }
                    if current_aliases & profile.service_names:
                        lineage_score = 0.75
            contributors["service_lineage"] = round(lineage_score * 0.34, 3)
            # trigger text similarity
            trigger_score = 0.0
            if trigger and profile.trigger.lower() == trigger:
                trigger_score = 1.0
            elif trigger and trigger[:20] in profile.trigger.lower():
                trigger_score = 0.45
            elif trigger_svc:
                hist_trigger_svc = _infer_service_from_trigger(profile.trigger)
                if hist_trigger_svc and hist_trigger_svc == trigger_svc:
                    trigger_score = 0.70
                elif trigger_svc in profile.service_names:
                    trigger_score = 0.55
            contributors["trigger"] = round(trigger_score * 0.16, 3)
            # behavioral signature similarity
            sig_sim, sig_audit = tmp.sig_similarity_details(profile)
            shape_score, shape_audit = self._shape_score(tmp, profile)
            temporal_score = 1.0 if shape_audit["components"].get("delay_bucket") == 1.0 else 0.0
            remediation_score = 1.0 if profile.resolved else 0.25 if profile.remediations else 0.0
            match_score = (
                lineage_score * 0.34
                + shape_score * 0.38
                + trigger_score * 0.16
                + temporal_score * 0.07
                + remediation_score * 0.05
            )
            recall_guard_score = (
                (1.0 if lineage_score else 0.0) * 0.30
                + sig_sim * 0.45
                + trigger_score * 0.25
            )
            contributors["behavioral_signature"] = round(shape_score * 0.38, 3)
            contributors["temporal_sequence"] = round(temporal_score * 0.07, 3)
            contributors["remediation_transfer"] = round(remediation_score * 0.05, 3)

            if max(match_score, recall_guard_score) >= 0.25:
                matches.append({
                    "incident_id": iid,
                    "past_incident_id": iid,
                    "similarity": _confidence(match_score),
                    "match_score": round(match_score, 3),
                    "shape_score": round(shape_score, 3),
                    "lineage_score": round(lineage_score, 3),
                    "recall_guard_score": round(recall_guard_score, 3),
                    "fallback_diversification": False,
                    "rationale": self._rationale(canonical, profile, shape_score, live_cans if canonical else set()),
                    "audit": {
                        "matched_service_lineage": bool(canonical and canonical in live_cans),
                        "lineage_candidates": sorted(live_cans),
                        "matched_temporal_sequence": self._sequence_audit(tmp, profile),
                        "matched_behavioral_signature": sig_audit,
                        "matched_shape": shape_audit,
                        "remediation_history": self._profile_remediation_audit(profile),
                        "confidence_contributors": contributors,
                    },
                })

        return self._rank_matches(matches, limit=5)

    @staticmethod
    def _shape_score(current: "_IncidentProfile", historical: "_IncidentProfile") -> tuple[float, dict]:
        cur = current.signature()
        hist = historical.signature()
        components = {
            "has_deploy": 1.0 if cur.get("has_deploy") == hist.get("has_deploy") else 0.0,
            "delay_bucket": 1.0 if cur.get("delay_bucket") == hist.get("delay_bucket") else 0.0,
            "metric_class": _jaccard(cur.get("metric_class"), hist.get("metric_class")),
            "log_class": _jaccard(cur.get("log_class"), hist.get("log_class")),
            "trace_class": _jaccard(cur.get("trace_class"), hist.get("trace_class")),
            "remediation_types": _jaccard(cur.get("remediation_types"), hist.get("remediation_types")),
            "outcome_class": 1.0 if cur.get("outcome_class") == hist.get("outcome_class") else 0.0,
        }
        weights = {
            "has_deploy": 1.0,
            "delay_bucket": 2.0,
            "metric_class": 2.5,
            "log_class": 2.0,
            "trace_class": 1.0,
            "remediation_types": 0.5,
            "outcome_class": 0.25,
        }
        score = sum(components[k] * weights[k] for k in weights) / sum(weights.values())
        return score, {
            "current_shape_key": cur.get("shape_key"),
            "historical_shape_key": hist.get("shape_key"),
            "exact_shape_key_match": cur.get("shape_key") == hist.get("shape_key"),
            "components": {k: round(v, 3) for k, v in components.items()},
        }

    @staticmethod
    def _rank_matches(matches: list[dict], limit: int) -> list[dict]:
        ordered = sorted(
            matches,
            key=lambda m: (
                -m.get("match_score", m.get("similarity", 0)),
                -m.get("shape_score", 0),
                -m.get("lineage_score", 0),
                m["incident_id"],
            ),
        )
        family_ids = {_incident_family(m.get("incident_id", "")) for m in ordered}
        if len(family_ids) <= limit:
            by_family: dict[object, list[dict]] = defaultdict(list)
            for match in ordered:
                by_family[_incident_family(match.get("incident_id", ""))].append(match)
            out = []
            for fam in sorted(
                by_family,
                key=lambda f: (-by_family[f][0].get("recall_guard_score", 0), -by_family[f][0].get("match_score", 0), str(f)),
            ):
                item = dict(by_family[fam][0])
                item["fallback_diversification"] = item.get("match_score", 0.0) < 0.45
                item.setdefault("audit", {}).setdefault("ranking", {})["fallback_reason"] = (
                    "recall_guard_family_coverage" if item["fallback_diversification"] else ""
                )
                out.append(item)
                if len(out) == limit:
                    break
            return out

        out = []
        used_ids = set()

        def add(item, fallback: bool = False):
            if item["incident_id"] in used_ids or len(out) >= limit:
                return
            item = dict(item)
            item["fallback_diversification"] = fallback
            item.setdefault("audit", {}).setdefault("ranking", {})["fallback_reason"] = (
                "recall_guard_family_diversification" if fallback else ""
            )
            out.append(item)
            used_ids.add(item["incident_id"])

        for item in ordered:
            if item.get("match_score", 0.0) >= 0.62:
                add(item)
        for item in ordered:
            if item.get("match_score", 0.0) >= 0.45:
                add(item)
        if len(out) >= limit:
            return out[:limit]

        fallback_ordered = sorted(
            [m for m in matches if m["incident_id"] not in used_ids],
            key=lambda m: (-m.get("recall_guard_score", 0), -m.get("match_score", 0), m["incident_id"]),
        )
        by_family: dict[object, list[dict]] = defaultdict(list)
        for match in fallback_ordered:
            by_family[_incident_family(match.get("incident_id", ""))].append(match)
        families = sorted(
            by_family,
            key=lambda fam: (-by_family[fam][0].get("recall_guard_score", 0), str(fam)),
        )
        for fam in families:
            add(by_family[fam][0], fallback=True)

        for item in fallback_ordered:
            add(item, fallback=True)
        return out

    @staticmethod
    def _rationale(canonical: str, profile: "_IncidentProfile", sig_sim: float, live_cans: set[str]) -> str:
        parts = []
        if canonical and canonical in profile.affected_canonical:
            parts.append("same canonical service")
        elif canonical and canonical in live_cans:
            parts.append("same service lineage after rename")
        if sig_sim >= 0.7:
            parts.append("high behavioral signature match")
        elif sig_sim >= 0.4:
            parts.append("partial behavioral match")
        if profile.resolved:
            parts.append("was resolved")
        return "; ".join(parts) if parts else "matched incident memory"

    @staticmethod
    def _sequence_audit(current: "_IncidentProfile", historical: "_IncidentProfile") -> dict:
        cur = current.signature()
        hist = historical.signature()
        return {
            "current_delay_bucket": cur.get("delay_bucket"),
            "historical_delay_bucket": hist.get("delay_bucket"),
            "delay_bucket_matched": cur.get("delay_bucket") == hist.get("delay_bucket"),
            "current_has_deploy": cur.get("has_deploy"),
            "historical_has_deploy": hist.get("has_deploy"),
            "current_has_trace": cur.get("has_trace"),
            "historical_has_trace": hist.get("has_trace"),
        }

    @staticmethod
    def _profile_remediation_audit(profile: "_IncidentProfile") -> dict:
        actions = Counter()
        successes = failures = 0
        latest = ""
        for event in profile.remediations:
            attrs = event.get("attributes", {})
            action = str(attrs.get("action", "")).lower()
            outcome = str(attrs.get("outcome", "")).lower()
            if action:
                actions[action] += 1
            if outcome in ("resolved", "success", "worked"):
                successes += 1
            elif outcome == "failed":
                failures += 1
            latest = outcome or latest
        return {
            "actions": dict(actions),
            "success_count": successes,
            "failure_count": failures,
            "latest_outcome": latest,
            "resolved": profile.resolved,
        }

    # ------------------------------------------------------------------
    # Internal: remediation ranking
    # ------------------------------------------------------------------

    def _remediations(self, sig: dict, similar: list, aliases: set, sig_ts: datetime) -> list:
        similar_ids = {m["past_incident_id"] for m in similar}
        canonical = sig.get("canonical_service_id", "")
        svc = sig.get("service_name", "")
        low_aliases = {a.lower() for a in aliases}

        grouped: dict[tuple, dict] = {}
        for rec in self._feedback:
            if rec["tenant_id"] != sig["tenant_id"] or rec["environment"] != sig["environment"]:
                continue
            score = 0.15
            rec_can = rec.get("canonical_service_id", "")
            rec_tgt = rec.get("target", "").lower()
            rec_svc = rec.get("service_name", "").lower()
            if canonical and rec_can == canonical:
                score += 0.40
            elif rec_tgt in low_aliases or rec_svc in low_aliases:
                score += 0.30
            if rec.get("incident_id") in similar_ids:
                score += 0.25
            outcome = rec.get("outcome", "").lower()
            if outcome in ("resolved", "success", "worked"):
                score += 0.15
            elif outcome == "failed":
                score -= 0.20
            age_days = max(0, (sig_ts - _parse_ts(rec["observed_at"])).days)
            age_decay = max(0.55, 1.0 - (age_days / 365) * 0.25)
            score *= age_decay
            # remap target to current service name
            target = rec.get("target", "")
            if svc and (rec_can == canonical or rec_tgt in low_aliases):
                target = svc
            key = (rec.get("action", ""), target)
            item = {"action": key[0], "target": target,
                    "historical_outcome": rec.get("outcome", ""), "confidence": _confidence(score),
                    "audit": {
                        "basis_incident_id": rec.get("incident_id", ""),
                        "same_lineage": bool(canonical and rec_can == canonical),
                        "similar_incident_basis": rec.get("incident_id") in similar_ids,
                        "success_count": 1 if outcome in ("resolved", "success", "worked") else 0,
                        "failure_count": 1 if outcome == "failed" else 0,
                        "age_days": age_days,
                        "age_decay": round(age_decay, 3),
                        "target_remapped": bool(target and target != rec.get("target", "")),
                        "confidence_contributors": {
                            "lineage_or_alias": 0.40 if canonical and rec_can == canonical else 0.30 if rec_tgt in low_aliases or rec_svc in low_aliases else 0.0,
                            "similar_incident": 0.25 if rec.get("incident_id") in similar_ids else 0.0,
                            "outcome": 0.15 if outcome in ("resolved", "success", "worked") else -0.20 if outcome == "failed" else 0.0,
                        },
                    }}
            if key not in grouped or item["confidence"] > grouped[key]["confidence"]:
                grouped[key] = item

        # fallback heuristic when nothing matches yet
        if not grouped:
            trigger = sig.get("trigger", "").lower()
            action = "rollback" if "deploy" in trigger or "version" in trigger else "inspect_service"
            grouped[action, svc or "unknown"] = {
                "action": action, "target": svc or "unknown",
                "historical_outcome": "unknown", "confidence": 0.20,
                "audit": {
                    "basis_incident_id": "",
                    "same_lineage": False,
                    "similar_incident_basis": False,
                    "success_count": 0,
                    "failure_count": 0,
                    "age_days": None,
                    "age_decay": None,
                    "target_remapped": False,
                    "confidence_contributors": {"fallback": 0.20},
                },
            }
        return sorted(grouped.values(), key=lambda r: (-r["confidence"], r["action"]))[:3]

    # ------------------------------------------------------------------
    # Internal: anomaly detectors
    # ------------------------------------------------------------------

    @staticmethod
    def _is_anomaly_metric(ev: dict) -> bool:
        return _metric_is_anomaly(ev)

    @staticmethod
    def _is_failure_log(ev: dict) -> bool:
        return _log_is_failure(ev)

    # ------------------------------------------------------------------
    # Internal: explain
    # ------------------------------------------------------------------

    @staticmethod
    def _explain(sig: dict, related: list, causal: list, similar: list, remeds: list) -> str:
        svc = sig.get("service_name") or sig.get("canonical_service_id") or "unknown service"
        parts = [f"Reconstructed {sig['incident_id'] or 'incident'} for {svc} using {len(related)} events"]
        if causal:
            evidence = causal[0].get("evidence", ["causal evidence"])[0].replace("_", " ")
            parts.append(f"{len(causal)} causal edges synthesized; strongest evidence is {evidence}")
        if similar:
            top = similar[0]
            parts.append(f"closest match: {top['past_incident_id']} ({int(top['similarity']*100)}% similar: {top.get('rationale', 'matched memory')})")
        if remeds:
            r = remeds[0]
            parts.append(f"top remediation: {r['action']} on {r['target']} because historical outcome was {r.get('historical_outcome', 'unknown')} (confidence {int(r['confidence']*100)}%)")
        return "; ".join(parts) + "."
