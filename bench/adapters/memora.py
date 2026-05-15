from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Iterable


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
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _canonical_name(service):
    return f"svc:{str(service).lower()}" if service else ""


def _confidence(value):
    return round(max(0.0, min(1.0, value)), 2)


class _AliasGraph:
    def __init__(self):
        self.canonical = {}
        self.adj = {}

    def upsert(self, tenant, env, source, target):
        if not source or not target:
            return
        a = self._key(tenant, env, source)
        b = self._key(tenant, env, target)
        canonical = _canonical_name(target)
        self.canonical[a] = canonical
        self.canonical[b] = canonical
        self.adj.setdefault(a, set()).add(b)
        self.adj.setdefault(b, set()).add(a)
        for key in self._connected(a):
            self.canonical[key] = canonical

    def resolve(self, tenant, env, service):
        if not service:
            return ""
        return self.canonical.get(self._key(tenant, env, service), _canonical_name(service))

    def aliases(self, tenant, env, service):
        if not service:
            return []
        start = self._key(tenant, env, service)
        seen = {start}
        q = deque([start])
        out = []
        while q:
            cur = q.popleft()
            out.append(cur.split("|", 2)[-1])
            for nxt in self.adj.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        return sorted(set(out))

    def _connected(self, start):
        seen = {start}
        q = deque([start])
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


class Engine:
    def __init__(self):
        self.events = []
        self.aliases = _AliasGraph()
        self.memories = {}
        self.feedback = []

    def ingest(self, events: Iterable[dict]) -> None:
        for raw in events:
            event = self._normalize(raw)
            if event["kind"] == "topology" and event["attributes"].get("change") == "rename":
                self.aliases.upsert(
                    event["tenant_id"],
                    event["environment"],
                    event["attributes"].get("from"),
                    event["attributes"].get("to"),
                )
                event["canonical_service_id"] = self.aliases.resolve(
                    event["tenant_id"], event["environment"], event["attributes"].get("to")
                )
            elif event["service_name"]:
                event["canonical_service_id"] = self.aliases.resolve(
                    event["tenant_id"], event["environment"], event["service_name"]
                )
            self.events.append(event)
            if event["kind"] == "remediation":
                self.feedback.append({
                    "incident_id": event.get("incident_id", ""),
                    "tenant_id": event["tenant_id"],
                    "environment": event["environment"],
                    "action": event["attributes"].get("action", ""),
                    "target": event["attributes"].get("target", event.get("service_name", "")),
                    "outcome": event["attributes"].get("outcome", ""),
                    "version": event["attributes"].get("version", ""),
                    "observed_at": event["ts"],
                    "service_name": event.get("service_name", ""),
                    "canonical_service_id": event.get("canonical_service_id", ""),
                })
        self.events.sort(key=lambda e: (e["ts"], e["event_id"]))

    def ingest_jsonl(self, text: str) -> None:
        """Ingest events from a JSONL string (one JSON object per line).

        Each line is parsed as a raw event dict and passed through the standard
        normalization path.  Blank lines and lines starting with ``#`` are
        silently skipped, making the format forgiving for hand-edited files.
        """
        events = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL line: {line!r}") from exc
        self.ingest(events)

    def ingest_file(self, path: str) -> None:
        """Ingest events from a JSONL file on disk."""
        import pathlib
        self.ingest_jsonl(pathlib.Path(path).read_text(encoding="utf-8"))



    def reconstruct_context(self, signal: dict, mode: str = "fast") -> dict:
        signal = self._normalize_signal(signal)
        window = timedelta(minutes=30 if mode == "fast" else 240)
        from_ts = _parse_ts(signal["ts"]) - window
        to_ts = _parse_ts(signal["ts"]) + timedelta(minutes=10)
        services = set(filter(None, [
            signal.get("service_name", ""),
            signal.get("canonical_service_id", ""),
            *self.aliases.aliases(signal["tenant_id"], signal["environment"], signal.get("service_name", "")),
        ]))
        candidates = [
            e for e in self.events
            if e["tenant_id"] == signal["tenant_id"]
            and e["environment"] == signal["environment"]
            and from_ts <= _parse_ts(e["ts"]) <= to_ts
            and (not services or self._event_matches_services(e, services))
            and (not e.get("incident_id") or e.get("incident_id") == signal["incident_id"])
        ]
        related = self._rank_related(signal, candidates)
        causal = self._causal_edges(related)
        similar = self._similar(signal, related)
        remediations = self._remediations(signal, similar)
        confidence = _confidence(
            0.15 + min(0.30, len(related) * 0.03)
            + min(0.25, len(causal) * 0.08)
            + min(0.20, len(similar) * 0.06)
            + min(0.10, len(remediations) * 0.04)
        )
        context = {
            "related_events": related,
            "causal_chain": causal,
            "similar_past_incidents": similar,
            "suggested_remediations": remediations,
            "confidence": confidence,
            "explain": self._explain(signal, related, similar, remediations),
        }
        self.memories[signal["incident_id"]] = {"signal": signal, "context": context}
        return context

    def close(self):
        return None

    def _normalize(self, raw):
        attrs = dict(raw.get("attributes") or {})
        kind = raw.get("kind", "")
        service = raw.get("service_name") or raw.get("service") or raw.get("svc") or ""
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
            if not service and raw.get("spans"):
                service = raw["spans"][0].get("svc", "")
        elif kind == "topology":
            attrs.setdefault("change", raw.get("change", ""))
            attrs.setdefault("from", raw.get("from", ""))
            attrs.setdefault("to", raw.get("to", ""))
            service = service or attrs.get("to", "")
        elif kind == "remediation":
            attrs.setdefault("action", raw.get("action", ""))
            attrs.setdefault("target", raw.get("target", service))
            attrs.setdefault("version", raw.get("version", ""))
            attrs.setdefault("outcome", raw.get("outcome", ""))
            service = service or attrs.get("target", "")
        entities = set(raw.get("entities") or [])
        for span in attrs.get("spans", []) or []:
            if span.get("svc"):
                entities.add(span["svc"])
        for value in attrs.values():
            if isinstance(value, str) and "-svc" in value:
                for token in value.replace(":", " ").replace(",", " ").split():
                    if "-svc" in token:
                        entities.add(token.strip())
        tenant = raw.get("tenant_id", "default")
        env = raw.get("environment", "prod")
        event = {
            "event_id": raw.get("event_id") or _stable_id(raw),
            "ts": _iso(raw.get("ts")),
            "kind": kind,
            "tenant_id": tenant,
            "environment": env,
            "service_name": service,
            "canonical_service_id": raw.get("canonical_service_id", ""),
            "incident_id": raw.get("incident_id") or attrs.get("incident_id", ""),
            "trace_id": raw.get("trace_id", ""),
            "entities": sorted(entities),
            "attributes": attrs,
            "raw_ref": raw.get("raw_ref", ""),
            "provenance": raw.get("provenance") or {"source": "benchmark", "raw_kind": kind},
        }
        return event

    def _normalize_signal(self, signal):
        attrs = signal.get("attributes") or {}
        service = signal.get("service_name") or signal.get("service") or attrs.get("service") or ""
        tenant = signal.get("tenant_id", "default")
        env = signal.get("environment", "prod")
        canonical = signal.get("canonical_service_id") or self.aliases.resolve(tenant, env, service)
        return {
            "incident_id": signal.get("incident_id", ""),
            "ts": _iso(signal.get("ts")),
            "tenant_id": tenant,
            "environment": env,
            "service_name": service,
            "canonical_service_id": canonical,
            "trigger": signal.get("trigger", ""),
            "attributes": attrs,
        }

    def _event_matches_services(self, event, services):
        blob = json.dumps(event.get("attributes", {}), sort_keys=True).lower()
        return (
            event.get("service_name") in services
            or event.get("canonical_service_id") in services
            or bool(set(event.get("entities", [])) & services)
            or any(str(s).lower() in blob for s in services)
        )

    def _rank_related(self, signal, events):
        scored = []
        sig_ts = _parse_ts(signal["ts"])
        for event in events:
            score = 0.0
            if event.get("canonical_service_id") == signal.get("canonical_service_id"):
                score += 0.35
            if event.get("service_name", "").lower() == signal.get("service_name", "").lower():
                score += 0.20
            if event.get("incident_id") == signal.get("incident_id"):
                score += 0.20
            if signal.get("trigger", "").lower() in json.dumps(event.get("attributes", {})).lower():
                score += 0.10
            score += {"deploy": 0.15, "metric": 0.15, "log": 0.12, "trace": 0.12, "remediation": 0.08}.get(event["kind"], 0)
            delta = abs((sig_ts - _parse_ts(event["ts"])).total_seconds() / 60)
            score += max(0, 0.18 - delta / 180)
            if score >= 0.2:
                scored.append((score, delta, event))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]["event_id"]))
        deduped = []
        seen = set()
        for _, _, event in scored:
            if event["event_id"] in seen:
                continue
            seen.add(event["event_id"])
            deduped.append(event)
            if len(deduped) == 12:
                break
        return sorted(deduped, key=lambda e: (e["ts"], e["event_id"]))

    def _causal_edges(self, events):
        deploys = [e for e in events if e["kind"] == "deploy"]
        anomalies = [e for e in events if e["kind"] == "metric" and self._metric_spike(e)]
        failures = [e for e in events if (e["kind"] == "log" and self._log_failure(e)) or (e["kind"] == "trace" and self._trace_latency(e))]
        edges = []
        for deploy in deploys:
            for anomaly in anomalies:
                if _parse_ts(deploy["ts"]) < _parse_ts(anomaly["ts"]):
                    edges.append({"cause_id": deploy["event_id"], "effect_id": anomaly["event_id"], "evidence": ["deploy_precedes_metric_spike"], "confidence": 0.72})
        for anomaly in anomalies:
            for failure in failures:
                if _parse_ts(anomaly["ts"]) < _parse_ts(failure["ts"]):
                    edges.append({"cause_id": anomaly["event_id"], "effect_id": failure["event_id"], "evidence": ["metric_or_trace_precedes_upstream_failure"], "confidence": 0.68})
        return sorted(edges, key=lambda e: (-e["confidence"], e["cause_id"] + e["effect_id"]))[:8]

    def _similar(self, signal, related):
        current = set(self._shape_tokens(related))
        matches = []
        for memory in self.memories.values():
            past = memory["signal"]
            if past["incident_id"] == signal["incident_id"]:
                continue
            score = 0.0
            if past.get("canonical_service_id") == signal.get("canonical_service_id"):
                score += 0.35
            if past.get("trigger", "").lower() == signal.get("trigger", "").lower():
                score += 0.25
            shared = current & set(self._shape_tokens(memory["context"].get("related_events", [])))
            score += min(0.30, len(shared) * 0.06)
            if score >= 0.35:
                matches.append({"past_incident_id": past["incident_id"], "similarity": _confidence(score), "rationale": "matched canonical lineage and behavioral shape"})
        return sorted(matches, key=lambda m: (-m["similarity"], m["past_incident_id"]))[:5]

    def _remediations(self, signal, similar):
        similar_ids = {m["past_incident_id"] for m in similar}
        grouped = {}
        sig_ts = _parse_ts(signal["ts"])
        aliases = {a.lower() for a in self.aliases.aliases(signal["tenant_id"], signal["environment"], signal.get("service_name", ""))}
        for record in self.feedback:
            if record["tenant_id"] != signal["tenant_id"] or record["environment"] != signal["environment"]:
                continue
            score = 0.2
            if record.get("canonical_service_id") == signal.get("canonical_service_id"):
                score += 0.35
            elif record.get("target", "").lower() in aliases:
                score += 0.35
            elif record.get("service_name", "").lower() in aliases:
                score += 0.25
            if record.get("incident_id") in similar_ids:
                score += 0.30
            outcome = record.get("outcome", "").lower()
            if outcome in ("resolved", "success", "worked"):
                score += 0.15
            elif outcome == "failed":
                score -= 0.15
            age = max(0, (sig_ts - _parse_ts(record["observed_at"])).days)
            score *= max(0.55, 1 - (age / 365) * 0.25)
            target = record.get("target", "")
            if signal.get("service_name") and (
                record.get("canonical_service_id") == signal.get("canonical_service_id")
                or record.get("target", "").lower() in aliases
            ):
                target = signal["service_name"]
            key = (record.get("action", ""), target)
            item = {"action": key[0], "target": key[1], "historical_outcome": record.get("outcome", ""), "confidence": _confidence(score)}
            if key not in grouped or item["confidence"] > grouped[key]["confidence"]:
                grouped[key] = item
        if not grouped and signal.get("service_name"):
            grouped[("inspect_recent_deploy_or_rollback", signal["service_name"])] = {
                "action": "inspect_recent_deploy_or_rollback",
                "target": signal["service_name"],
                "historical_outcome": "unknown",
                "confidence": 0.25,
            }
        return sorted(grouped.values(), key=lambda r: (-r["confidence"], r["action"] + r["target"]))[:3]

    def _shape_tokens(self, events):
        tokens = set()
        deploy_ts = None
        for event in events:
            kind = event.get("kind")
            attrs = event.get("attributes", {})
            if kind == "deploy":
                tokens.add("deploy")
                deploy_ts = _parse_ts(event["ts"]) if deploy_ts is None else min(deploy_ts, _parse_ts(event["ts"]))
            if kind == "metric":
                name = str(attrs.get("name", "")).lower()
                if "latency" in name or self._metric_spike(event):
                    tokens.add("latency-spike")
                if "error" in name:
                    tokens.add("error-rate")
            if kind == "log" and self._log_failure(event):
                tokens.add("upstream-failure")
            if kind == "trace" and self._trace_latency(event):
                tokens.add("trace-latency")
            if deploy_ts and _parse_ts(event["ts"]) > deploy_ts and _parse_ts(event["ts"]) - deploy_ts <= timedelta(minutes=10):
                tokens.add("post-deploy-window")
        return sorted(tokens)

    @staticmethod
    def _metric_spike(event):
        try:
            return float(event.get("attributes", {}).get("value", 0)) >= 1000
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _log_failure(event):
        attrs = event.get("attributes", {})
        msg = str(attrs.get("msg", "")).lower()
        level = str(attrs.get("level", "")).lower()
        return "timeout" in msg or "error" in msg or level == "error"

    @staticmethod
    def _trace_latency(event):
        return "dur_ms" in json.dumps(event.get("attributes", {})).lower()

    @staticmethod
    def _explain(signal, related, similar, remediations):
        parts = [f"Incident {signal['incident_id']} was reconstructed using {len(related)} related events"]
        if similar:
            parts.append(f"{len(similar)} similar incidents matched")
        if remediations:
            parts.append(f"top remediation is {remediations[0]['action']} on {remediations[0]['target']}")
        return "; ".join(parts) + "."
