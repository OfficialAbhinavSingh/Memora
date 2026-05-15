from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
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


def _infer_service_from_events(events: list, window_ts: datetime, window: timedelta) -> str:
    """Pick the most-mentioned service in nearby events."""
    counts: dict[str, int] = defaultdict(int)
    lo, hi = window_ts - window, window_ts + window
    for e in events:
        if not (lo <= _parse_ts(e["ts"]) <= hi):
            continue
        svc = e.get("service_name") or e.get("canonical_service_id", "")
        if svc:
            counts[svc] += 1
    return max(counts, key=counts.__getitem__) if counts else ""


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
        self.remediations: list[dict] = []
        self.affected_canonical: set[str] = set()
        self.trigger: str = ""
        self.first_ts: str = ""
        self.last_ts: str = ""
        self.resolved: bool = False
        self._sig: dict = {}

    def add(self, event: dict) -> None:
        self.events.append(event)
        if c := event.get("canonical_service_id"):
            self.affected_canonical.add(c)
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
        metric_cls, log_cls = set(), set()
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
        self._sig = {
            "has_deploy": "deploy" in kinds,
            "has_metric": "metric" in kinds,
            "has_trace": "trace" in kinds,
            "has_log": "log" in kinds,
            "has_remediation": bool(self.remediations),
            "delay_bucket": delay,
            "metric_class": sorted(metric_cls),
            "log_class": sorted(log_cls),
            "remediation_types": sorted({
                str(r.get("attributes", {}).get("action", "")).lower()
                for r in self.remediations
            }),
            "resolved": self.resolved,
        }
        return self._sig

    def sig_similarity(self, other: "_IncidentProfile") -> float:
        a, b = self.signature(), other.signature()
        score = weight = 0.0

        def bm(k, w):
            nonlocal score, weight
            weight += w
            if a.get(k) == b.get(k):
                score += w

        def sm(k, w):
            nonlocal score, weight
            weight += w
            sa, sb = set(a.get(k, [])), set(b.get(k, []))
            score += w * (len(sa & sb) / max(len(sa | sb), 1) if (sa or sb) else 1.0)

        bm("has_deploy", 1.5)
        bm("delay_bucket", 2.0)
        sm("metric_class", 2.5)
        sm("log_class", 2.0)
        bm("has_remediation", 1.0)
        sm("remediation_types", 1.5)
        bm("resolved", 0.5)
        return score / weight if weight else 0.0

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
        batch = []
        for raw in events:
            ev = self._normalize(raw)
            self._resolve_canonical(ev)
            self._events.append(ev)
            batch.append(ev)
            # update indexes
            if c := ev.get("canonical_service_id"):
                self._by_service[c].append(ev)
            if iid := ev.get("incident_id"):
                self._by_incident[iid].append(ev)
                self._update_profile(iid, ev)
            if ev["kind"] == "remediation":
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
        # sort just new batch's range (already sorted prefix)
        self._events.sort(key=lambda e: (e["ts"], e["event_id"]))

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
        if not svc:
            svc = _infer_service_from_trigger(sig.get("trigger", ""))
        if not svc:
            svc = _infer_service_from_events(self._events, sig_ts, window)
        if svc:
            sig["service_name"] = svc
            sig["canonical_service_id"] = self._aliases.resolve(
                sig["tenant_id"], sig["environment"], svc
            )

        canonical = sig.get("canonical_service_id", "")
        all_aliases = set(self._aliases.aliases(sig["tenant_id"], sig["environment"], svc))
        all_aliases.add(svc)
        if canonical:
            all_aliases.add(canonical)

        # candidates: same tenant/env in window, service-matched or incident-matched
        candidates = [
            e for e in self._events
            if e["tenant_id"] == sig["tenant_id"]
            and e["environment"] == sig["environment"]
            and lo <= _parse_ts(e["ts"]) <= hi
            and (
                not all_aliases
                or self._svc_match(e, all_aliases, canonical)
                or e.get("incident_id") == sig["incident_id"]
            )
        ]

        related = self._rank_related(sig, candidates, sig_ts)
        causal = self._causal_edges(related)
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
        self._profiles[incident_id].add(event)

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

    def _rank_related(self, sig: dict, candidates: list, sig_ts: datetime) -> list:
        canonical = sig.get("canonical_service_id", "")
        scored = []
        for ev in candidates:
            s = 0.0
            if ev.get("canonical_service_id") == canonical and canonical:
                s += 0.35
            if ev.get("service_name", "").lower() == sig.get("service_name", "").lower() and sig.get("service_name"):
                s += 0.20
            if ev.get("incident_id") and ev["incident_id"] == sig.get("incident_id"):
                s += 0.25
            trigger = sig.get("trigger", "").lower()
            if trigger and trigger in json.dumps(ev.get("attributes", {})).lower():
                s += 0.10
            s += {"deploy": 0.18, "metric": 0.16, "log": 0.14, "trace": 0.14, "remediation": 0.10}.get(ev["kind"], 0)
            delta = abs((sig_ts - _parse_ts(ev["ts"])).total_seconds() / 60)
            s += max(0, 0.20 - delta / 180)
            if s >= 0.15:
                scored.append((s, delta, ev))
        scored.sort(key=lambda x: (-x[0], x[1], x[2]["event_id"]))
        seen, out = set(), []
        for _, _, ev in scored:
            if ev["event_id"] not in seen:
                seen.add(ev["event_id"])
                out.append(ev)
                if len(out) == 15:
                    break
        return sorted(out, key=lambda e: (e["ts"], e["event_id"]))

    # ------------------------------------------------------------------
    # Internal: causal edges (more types than before)
    # ------------------------------------------------------------------

    def _causal_edges(self, events: list) -> list:
        deploys   = [e for e in events if e["kind"] == "deploy"]
        metrics   = [e for e in events if e["kind"] == "metric" and self._is_anomaly_metric(e)]
        logs      = [e for e in events if e["kind"] == "log" and self._is_failure_log(e)]
        traces    = [e for e in events if e["kind"] == "trace"]
        remeds    = [e for e in events if e["kind"] == "remediation"]
        edges = []

        def _ts(e): return _parse_ts(e["ts"])
        def _before(a, b, max_min=60): return 0 < (_ts(b) - _ts(a)).total_seconds() <= max_min * 60

        # deploy → metric spike
        for d in deploys:
            for m in metrics:
                if _before(d, m, 60):
                    edges.append({"cause_id": d["event_id"], "effect_id": m["event_id"],
                                  "evidence": ["deploy_precedes_metric_spike"], "confidence": 0.82})
        # deploy → log failure
        for d in deploys:
            for l in logs:
                if _before(d, l, 60):
                    edges.append({"cause_id": d["event_id"], "effect_id": l["event_id"],
                                  "evidence": ["deploy_precedes_log_failure"], "confidence": 0.75})
        # metric spike → upstream log failure
        for m in metrics:
            for l in logs:
                if _before(m, l, 30):
                    edges.append({"cause_id": m["event_id"], "effect_id": l["event_id"],
                                  "evidence": ["metric_spike_precedes_failure"], "confidence": 0.68})
        # trace caller → callee latency
        for t in traces:
            spans = t.get("attributes", {}).get("spans", []) or []
            if len(spans) >= 2:
                for i in range(len(spans) - 1):
                    caller_svc = spans[i].get("svc", "")
                    callee_svc = spans[i + 1].get("svc", "")
                    if caller_svc != callee_svc:
                        edges.append({"cause_id": t["event_id"], "effect_id": t["event_id"] + f"_span{i}",
                                      "evidence": [f"trace_caller_{caller_svc}_callee_{callee_svc}"], "confidence": 0.65})
        # log failure → remediation
        for l in logs:
            for r in remeds:
                if _before(l, r, 120):
                    edges.append({"cause_id": l["event_id"], "effect_id": r["event_id"],
                                  "evidence": ["failure_log_triggers_remediation"], "confidence": 0.70})
        # deduplicate by (cause, effect), keep highest confidence
        best: dict[tuple, dict] = {}
        for edge in edges:
            key = (edge["cause_id"], edge["effect_id"])
            if key not in best or edge["confidence"] > best[key]["confidence"]:
                best[key] = edge
        return sorted(best.values(), key=lambda e: (-e["confidence"], e["cause_id"]))[:8]

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
        matches = []

        for iid, profile in self._profiles.items():
            if iid == sig.get("incident_id"):
                continue
            if profile.tenant_id != sig["tenant_id"] or profile.environment != sig["environment"]:
                continue

            score = 0.0
            # canonical service match — resolve stored canonicals through the
            # CURRENT alias graph so renamed services (payments-svc -> billing-svc)
            # still match historical profiles built pre-rename.
            if canonical:
                live_cans = {
                    self._aliases.canonical.get(c, c)
                    for c in profile.affected_canonical
                }
                if canonical in live_cans:
                    score += 0.30
            # trigger text similarity
            if trigger and profile.trigger.lower() == trigger:
                score += 0.25
            elif trigger and trigger[:20] in profile.trigger.lower():
                score += 0.12
            # behavioral signature similarity
            sig_sim = tmp.sig_similarity(profile)
            score += sig_sim * 0.45

            if score >= 0.25:
                matches.append({
                    "past_incident_id": iid,
                    "similarity": _confidence(score),
                    "rationale": self._rationale(canonical, profile, sig_sim),
                })

        return sorted(matches, key=lambda m: (-m["similarity"], m["past_incident_id"]))[:5]

    @staticmethod
    def _rationale(canonical: str, profile: "_IncidentProfile", sig_sim: float) -> str:
        parts = []
        if canonical and canonical in profile.affected_canonical:
            parts.append("same canonical service")
        if sig_sim >= 0.7:
            parts.append("high behavioral signature match")
        elif sig_sim >= 0.4:
            parts.append("partial behavioral match")
        if profile.resolved:
            parts.append("was resolved")
        return "; ".join(parts) if parts else "matched incident memory"

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
            score *= max(0.55, 1.0 - (age_days / 365) * 0.25)
            # remap target to current service name
            target = rec.get("target", "")
            if svc and (rec_can == canonical or rec_tgt in low_aliases):
                target = svc
            key = (rec.get("action", ""), target)
            item = {"action": key[0], "target": target,
                    "historical_outcome": rec.get("outcome", ""), "confidence": _confidence(score)}
            if key not in grouped or item["confidence"] > grouped[key]["confidence"]:
                grouped[key] = item

        # fallback heuristic when nothing matches yet
        if not grouped:
            trigger = sig.get("trigger", "").lower()
            action = "rollback" if "deploy" in trigger or "version" in trigger else "inspect_service"
            grouped[action, svc or "unknown"] = {
                "action": action, "target": svc or "unknown",
                "historical_outcome": "unknown", "confidence": 0.20,
            }
        return sorted(grouped.values(), key=lambda r: (-r["confidence"], r["action"]))[:3]

    # ------------------------------------------------------------------
    # Internal: anomaly detectors
    # ------------------------------------------------------------------

    @staticmethod
    def _is_anomaly_metric(ev: dict) -> bool:
        a = ev.get("attributes", {})
        name = str(a.get("name", "")).lower()
        # error-rate style: value is a percentage string or float > threshold
        val_raw = a.get("value", 0)
        try:
            val = float(str(val_raw).rstrip("%"))
        except (TypeError, ValueError):
            val = 0.0
        if "error" in name or "failure" in name:
            return val > 1.0  # >1% error rate
        if "latency" in name or "p99" in name or "p95" in name or "ms" in name:
            return val > 200  # >200ms
        return val >= 1000  # generic spike

    @staticmethod
    def _is_failure_log(ev: dict) -> bool:
        a = ev.get("attributes", {})
        msg = str(a.get("msg", a.get("message", ""))).lower()
        level = str(a.get("level", "")).lower()
        return (
            level in ("error", "fatal", "critical")
            or any(k in msg for k in ("timeout", "refused", "error", "exception", "failed", "5xx", "500"))
        )

    # ------------------------------------------------------------------
    # Internal: explain
    # ------------------------------------------------------------------

    @staticmethod
    def _explain(sig: dict, related: list, causal: list, similar: list, remeds: list) -> str:
        svc = sig.get("service_name") or sig.get("canonical_service_id") or "unknown service"
        parts = [f"Reconstructed {sig['incident_id'] or 'incident'} for {svc} using {len(related)} events"]
        if causal:
            parts.append(f"{len(causal)} causal edges synthesized")
        if similar:
            top = similar[0]
            parts.append(f"closest match: {top['past_incident_id']} ({int(top['similarity']*100)}% similar)")
        if remeds:
            r = remeds[0]
            parts.append(f"top remediation: {r['action']} on {r['target']} (confidence {int(r['confidence']*100)}%)")
        return "; ".join(parts) + "."
