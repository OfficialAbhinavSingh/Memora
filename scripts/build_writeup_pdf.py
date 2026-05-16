"""Build the 3-page Anvil P-02 L3 writeup PDF from real numbers.

Usage:
    python scripts/build_writeup_pdf.py
    # writes docs/p02-writeup.pdf

Numbers are sourced from bench-p02-context/l3_report.json when present,
falling back to the values committed in docs/p02-writeup.md.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(REPO, "bench-p02-context", "l3_report.json")
OUT = os.path.join(REPO, "docs", "p02-writeup.pdf")

# ---------------------------------------------------------------------------
# Pull the real L3 numbers, fall back to the committed ones if absent
# ---------------------------------------------------------------------------

DEFAULTS = {
    "weighted_score": 0.3039,
    "max_automated": 0.80,
    "recall@5": 0.144,
    "precision@5_mean": 0.1408,
    "remediation_acc": 0.448,
    "latency_p95_ms": 62.0,
    "latency_mean_ms": 45.13,
    "latency_axis": 1.000,
    "n_signals_total": 125,
    "seeds": [314159, 271828, 161803, 141421, 173205],
    "per_seed": [
        {"seed": 314159, "recall@5": 0.120, "precision@5_mean": 0.120,
         "remediation_acc": 0.440, "latency_p95_ms": 47.0, "latency_mean_ms": 44.4},
        {"seed": 271828, "recall@5": 0.080, "precision@5_mean": 0.080,
         "remediation_acc": 0.400, "latency_p95_ms": 47.0, "latency_mean_ms": 45.0},
        {"seed": 161803, "recall@5": 0.200, "precision@5_mean": 0.200,
         "remediation_acc": 0.640, "latency_p95_ms": 47.0, "latency_mean_ms": 46.3},
        {"seed": 141421, "recall@5": 0.160, "precision@5_mean": 0.152,
         "remediation_acc": 0.360, "latency_p95_ms": 62.0, "latency_mean_ms": 45.6},
        {"seed": 173205, "recall@5": 0.160, "precision@5_mean": 0.152,
         "remediation_acc": 0.400, "latency_p95_ms": 47.0, "latency_mean_ms": 44.4},
    ],
    "l3_version": "anvil-2026-p02-L3-final",
    "timestamp": "2026-05-16",
    "adapter_path": "bench-p02-context/adapters/memora.py",
}


def _rel_adapter_path(p: str) -> str:
    if not p:
        return DEFAULTS["adapter_path"]
    p = p.replace("\\", "/")
    marker = "bench-p02-context/"
    if marker in p:
        return p[p.index(marker):]
    if "/" in p:
        return p.rsplit("/", 2)[-2] + "/" + p.rsplit("/", 1)[-1]
    return p


def load_numbers() -> dict:
    if not os.path.exists(REPORT):
        return DEFAULTS
    try:
        r = json.load(open(REPORT))
        agg = r["aggregated"]
        sc = r["score"]
        per_seed = []
        for s in r["per_seed"]:
            su = s["summary"]
            per_seed.append({
                "seed": s["seed"],
                "recall@5": su.get("recall@5", 0.0),
                "precision@5_mean": su.get("precision@5_mean", 0.0),
                "remediation_acc": su.get("remediation_acc", 0.0),
                "latency_p95_ms": su.get("latency_p95_ms", 0.0),
                "latency_mean_ms": su.get("latency_mean_ms", 0.0),
            })
        return {
            "weighted_score": sc.get("weighted_score", 0.0),
            "max_automated": sc.get("max_automated", 0.80),
            "recall@5": agg.get("recall@5", 0.0),
            "precision@5_mean": agg.get("precision@5_mean", 0.0),
            "remediation_acc": agg.get("remediation_acc", 0.0),
            "latency_p95_ms": agg.get("latency_p95_ms", 0.0),
            "latency_mean_ms": agg.get("latency_mean_ms", 0.0),
            "latency_axis": sc.get("axes", {}).get("latency_p95_ms", 1.0),
            "n_signals_total": agg.get("n_signals_total", 0),
            "seeds": r.get("seeds", []),
            "per_seed": per_seed,
            "l3_version": r.get("l3_version", "anvil-2026-p02-L3-final"),
            "timestamp": (r.get("timestamp", "") or "").split("T")[0]
                         or datetime.utcnow().strftime("%Y-%m-%d"),
            "adapter_path": _rel_adapter_path(
                r.get("adapter_path", DEFAULTS["adapter_path"])),
        }
    except Exception:
        return DEFAULTS


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

INDIGO = colors.HexColor("#3b2a7a")
INK = colors.HexColor("#1a1a2e")
MUTED = colors.HexColor("#5b5b6e")
ACCENT = colors.HexColor("#d97706")
LINE = colors.HexColor("#cbd0d9")
SOFT = colors.HexColor("#f3f1fa")


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=20, leading=24, textColor=INDIGO, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=10, leading=12, textColor=MUTED, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=12.5, leading=15, textColor=INDIGO,
            spaceBefore=10, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=13, textColor=INK,
            spaceBefore=6, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.4, leading=12.4, textColor=INK,
            alignment=TA_LEFT, spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.4, leading=12.4, textColor=INK,
            leftIndent=12, bulletIndent=2, spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "code", parent=base["Normal"], fontName="Courier",
            fontSize=8.6, leading=11, textColor=INK,
            backColor=SOFT, leftIndent=6, rightIndent=6,
            spaceBefore=4, spaceAfter=6,
        ),
        "score_label": ParagraphStyle(
            "score_label", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.5, textColor=MUTED, alignment=TA_CENTER, leading=10,
        ),
        "score_value": ParagraphStyle(
            "score_value", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=22, textColor=INDIGO, alignment=TA_CENTER, leading=24,
        ),
        "score_unit": ParagraphStyle(
            "score_unit", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.5, textColor=ACCENT, alignment=TA_CENTER, leading=10,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.8, textColor=MUTED, alignment=TA_CENTER,
        ),
        "footer_r": ParagraphStyle(
            "footer_r", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.8, textColor=MUTED, alignment=TA_RIGHT,
        ),
    }


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def score_card(n: dict, st: dict) -> Table:
    pct = (n["weighted_score"] / n["max_automated"]) * 100
    big = ParagraphStyle("big", parent=st["score_value"],
                         fontSize=18, leading=20)
    tag = ParagraphStyle("tag", parent=st["score_value"],
                         fontSize=7.2, leading=9,
                         fontName="Courier-Bold")
    cells = [
        [Paragraph("L3 Weighted Automated", st["score_label"]),
         Paragraph("Latency p95 (worst seed)", st["score_label"]),
         Paragraph("Remediation Accuracy", st["score_label"]),
         Paragraph("Release Tag", st["score_label"])],
        [Paragraph(f"{n['weighted_score']:.4f}<font size='10' "
                   f"color='#5b5b6e'> / {n['max_automated']:.2f}</font>",
                   big),
         Paragraph(f"{n['latency_p95_ms']:.0f}<font size='10' "
                   f"color='#5b5b6e'> ms</font>", big),
         Paragraph(f"{n['remediation_acc']*100:.1f}<font size='10' "
                   f"color='#5b5b6e'>%</font>", big),
         Paragraph(n['l3_version'], tag)],
        [Paragraph(f"{pct:.1f}% of max", st["score_unit"]),
         Paragraph("vs 2000 ms budget", st["score_unit"]),
         Paragraph("across 5 seeds", st["score_unit"]),
         Paragraph(f"run: {n['timestamp']}", st["score_unit"])],
    ]
    t = Table(cells, colWidths=[1.85*inch, 1.85*inch, 1.85*inch, 1.65*inch],
              hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("BOX", (0, 0), (-1, -1), 0.7, INDIGO),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def axes_table(n: dict, st: dict) -> Table:
    rows = [
        ["Axis", "Weight", "Score", "Contribution"],
        ["recall@5", "0.30", f"{n['recall@5']:.4f}",
         f"{0.30 * n['recall@5']:.4f}"],
        ["precision@5_mean", "0.15", f"{n['precision@5_mean']:.4f}",
         f"{0.15 * n['precision@5_mean']:.4f}"],
        ["remediation_acc", "0.20", f"{n['remediation_acc']:.4f}",
         f"{0.20 * n['remediation_acc']:.4f}"],
        [f"latency_p95 ({n['latency_p95_ms']:.0f} ms vs 2000 ms)",
         "0.15", f"{n['latency_axis']:.4f}",
         f"{0.15 * n['latency_axis']:.4f}"],
        ["manual_context", "0.10", "panel", "—"],
        ["manual_explain", "0.10", "panel", "—"],
        ["Weighted automated", "0.80", "",
         f"{n['weighted_score']:.4f}"],
    ]
    t = Table(rows, colWidths=[2.7*inch, 0.7*inch, 1.0*inch, 1.2*inch],
              hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8.8),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9),
        ("BACKGROUND", (0, -1), (-1, -1), SOFT),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, INDIGO),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, SOFT]),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def per_seed_table(n: dict, st: dict) -> Table:
    rows = [["Seed", "recall@5", "p@5", "rem_acc", "p95 ms", "mean ms"]]
    for s in n["per_seed"]:
        rows.append([
            str(s["seed"]),
            f"{s['recall@5']:.3f}",
            f"{s['precision@5_mean']:.3f}",
            f"{s['remediation_acc']:.3f}",
            f"{s['latency_p95_ms']:.0f}",
            f"{s['latency_mean_ms']:.1f}",
        ])
    t = Table(rows, colWidths=[1.0*inch, 0.85*inch, 0.75*inch,
                                0.85*inch, 0.75*inch, 0.85*inch],
              hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.8),
        ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("FONT", (0, 1), (-1, -1), "Courier", 8.6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def bullet(text: str, st: dict) -> Paragraph:
    return Paragraph(text, st["bullet"], bulletText="•")


def code(text: str, st: dict) -> Preformatted:
    return Preformatted(text, st["code"])


# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------

def make_doc(path: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        path, pagesize=LETTER,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.55*inch, bottomMargin=0.55*inch,
        title="Memora — Anvil P-02 L3 Final Writeup",
        author="Memora",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)

    def on_page(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(INDIGO)
        canvas.setLineWidth(1.4)
        canvas.line(doc.leftMargin, LETTER[1] - 0.42*inch,
                    LETTER[0] - doc.rightMargin, LETTER[1] - 0.42*inch)
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin, 0.30*inch,
                          "Memora · Anvil P-02 · anvil-2026-p02-L3-final")
        canvas.drawRightString(LETTER[0] - doc.rightMargin, 0.30*inch,
                               f"page {_doc.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame],
                                       onPage=on_page)])
    return doc


# ---------------------------------------------------------------------------
# Story
# ---------------------------------------------------------------------------

def build_story(n: dict, st: dict) -> list:
    s: list = []

    # Header / title
    s.append(Paragraph(
        "Memora — Persistent Context Engine for Autonomous SRE",
        st["title"]))
    s.append(Paragraph(
        "Anvil P-02 · L3 Final Writeup · "
        f"release tag <b>{n['l3_version']}</b>",
        st["subtitle"]))

    # Score card
    s.append(score_card(n, st))
    s.append(Spacer(1, 0.10 * inch))

    # Axes + per-seed tables — keep them side by side with axes wider
    axes = axes_table(n, st)
    seeds = per_seed_table(n, st)
    side = Table([[axes, seeds]],
                 colWidths=[5.7*inch, 5.05*inch - 5.7*inch + 0.05*inch])
    # Use a simpler vertical stack — side-by-side is too tight on letter
    s.append(axes)
    s.append(Spacer(1, 0.08 * inch))
    s.append(Paragraph(
        "<b>Per-seed breakdown</b> · 5 council seeds × 25 eval signals = "
        f"{n['n_signals_total']} reconstructions",
        st["body"]))
    s.append(seeds)
    s.append(Spacer(1, 0.10 * inch))

    # Section 1
    s.append(Paragraph("1. Memory Representation", st["h2"]))
    s.append(Paragraph(
        "Memora treats operational telemetry as evidence for long-lived "
        "incident memory, not as isolated records for keyword search. Every "
        "event is normalized at ingest into a stable envelope of timestamp, "
        "kind, service, canonical service id, incident id, trace id, "
        "extracted entities, attributes, and provenance hash, then routed "
        "into three structures formed during ingestion:", st["body"]))
    s.append(bullet(
        "a <b>service alias graph</b> that records every rename as an "
        "undirected edge and exposes BFS-resolved canonical lookup,",
        st))
    s.append(bullet(
        "a <b>per-incident profile</b> (<font face='Courier'>"
        "_IncidentProfile</font>) that accumulates nearby deploys, anomaly "
        "metrics, failure logs, traces, and remediations,",
        st))
    s.append(bullet(
        "a <b>service-keyed event index</b> for sub-millisecond temporal "
        "candidate generation at query time.",
        st))
    s.append(Paragraph(
        "Profiles are formed during ingestion, not lazily during query — "
        "the L3 harness ingests the entire training corpus once and then "
        "asks reconstruction queries only for held-out signals. The profile "
        "produces a topology-independent <b>behavioural signature</b>:",
        st["body"]))
    s.append(code(
        "shape_key = deploy | <5m | latency | timeout | callee | "
        "rollback | resolved",
        st))
    s.append(Paragraph(
        "Two incidents with the same shape key are operationally equivalent "
        "regardless of service names. There is no embedding model, no ANN "
        "index, no learned retriever — every match is reproducible from the "
        "inputs and fully inspectable.", st["body"]))

    # Section 2
    s.append(Paragraph("2. Relationship Synthesis", st["h2"]))
    s.append(Paragraph(
        "Reconstruction is a five-stage pipeline executed inside "
        "<font face='Courier'>Engine.reconstruct_context</font>:",
        st["body"]))
    s.append(bullet(
        "<b>Candidate generation</b> — pull events from a 30-min pre-signal "
        "/ 15-min post-signal window via "
        "<font face='Courier'>_by_service</font> lookups against the "
        "alias-resolved canonical and the full alias closure.",
        st))
    s.append(bullet(
        "<b>Related-event ranking</b> — score by lineage match, alias "
        "overlap, incident-id continuation, entity mention, anomaly "
        "strength, and temporal proximity to the signal.",
        st))
    s.append(bullet(
        "<b>Causal chain synthesis</b> — emit ordered evidence edges: "
        "deploy → metric spike, deploy → failure log, metric spike → "
        "upstream failure, trace caller↔callee, failure log → "
        "remediation. Each edge stores cause id, effect id, evidence "
        "label, confidence, and an ordering proof.",
        st))
    s.append(bullet(
        "<b>Similar-incident matching</b> — for every historical profile, "
        "compute (a) shape-key score and Jaccard-weighted component score "
        "across metric_class, log_class, trace_class, remediation_types, "
        "delay_bucket, has_deploy, has_remediation, resolved; (b) lineage "
        "score from canonical / alias overlap; (c) trigger-token agreement.",
        st))
    s.append(bullet(
        "<b>Remediation transfer</b> — rank historical remediations by "
        "lineage match, shape match, age decay, and the success/failure "
        "ledger; remap the target through the alias graph so a "
        "<font face='Courier'>payments-svc</font> rollback is transferred "
        "to the renamed <font face='Courier'>ledger-v2</font>.",
        st))
    s.append(Paragraph(
        "The whole pipeline is bounded — fast mode caps related events at "
        "10 and similar incidents at 5, which is what keeps the L3 "
        f"worst-seed p95 at <b>{n['latency_p95_ms']:.0f} ms</b>.",
        st["body"]))

    # Section 3
    s.append(Paragraph("3. Drift Handling Strategy", st["h2"]))
    s.append(Paragraph(
        "The single biggest test in P-02 is whether the engine recognises a "
        "recurring family when the underlying service has been renamed. L3 "
        "makes this strictly harder by enabling <b>cascading renames</b> — "
        "the same canonical service can be renamed two to four times across "
        "the 21-day timeline:", st["body"]))
    s.append(code(
        "payments-svc  →  billing-svc  →  ledger-v2  →  ledger-v2-r5\n"
        "                  (all four resolve to one canonical via BFS)",
        st))
    s.append(Paragraph(
        "Memora handles this with three layers:", st["body"]))
    s.append(bullet(
        "<b>Alias graph BFS.</b> "
        "<font face='Courier'>_AliasGraph</font> stores renames as "
        "undirected edges. <font face='Courier'>resolve()</font> and "
        "<font face='Courier'>aliases()</font> both run BFS from any input "
        "name, so every historical alias of a renamed service resolves to "
        "the same canonical and contributes evidence regardless of how "
        "many rename hops separate the train-time and eval-time names.",
        st))
    s.append(bullet(
        "<b>Behavioural shape matching.</b> When the alias chain breaks "
        "entirely (dependency drift renames the upstream caller, not the "
        "failing service), the topology-independent shape key still allows "
        "the historical incident to be found by behaviour alone.",
        st))
    s.append(bullet(
        "<b>Trigger-token inference.</b> When a signal arrives with only "
        "an alert string ("
        "<font face='Courier'>alert:svc-04-r3/latency_p99_ms&gt;3000</font>"
        "), <font face='Courier'>_infer_service_from_trigger</font> "
        "extracts the service token before any service-keyed lookup, so "
        "even bare signals participate in alias resolution.",
        st))
    s.append(Paragraph(
        "Contradictory remediation history is preserved rather than "
        "overwritten. Worked outcomes increase confidence; failed outcomes "
        "reduce it; older evidence decays. Each suggested remediation "
        "carries transfer proof: basis incident id, success/failure counts, "
        "target remapping through the alias graph, and the confidence "
        "contributors.", st["body"]))

    # Section 4
    s.append(Paragraph("4. Latency Engineering", st["h2"]))
    s.append(Paragraph(
        "The benchmark adapter is intentionally stdlib-only, "
        "single-process, CPU-only — no embedding service, no graph "
        "database call-out, NumPy is used only by the harness. Three "
        "engineering decisions keep latency far under budget on the L3 "
        "stretch config (30 services × 21 days × ~76k events × 25 query "
        "signals per seed):", st["body"]))
    s.append(bullet(
        "<b>Indexes built at ingest.</b> "
        "<font face='Courier'>_by_service</font>, "
        "<font face='Courier'>_by_incident</font>, and "
        "<font face='Courier'>_profiles</font> are built incrementally "
        "during <font face='Courier'>ingest()</font>, so reconstruction "
        "never scans the full event log.", st))
    s.append(bullet(
        "<b>Bounded windows.</b> Fast mode uses a 30-min pre-signal / "
        "15-min post-signal window. Even with cascading aliases, candidate "
        "generation touches a small slice of state.", st))
    s.append(bullet(
        "<b>Cached signatures.</b> "
        "<font face='Courier'>_IncidentProfile.signature()</font> "
        "memoises the shape key and component sets, so each historical "
        "incident is re-scored in microseconds.", st))
    s.append(Paragraph(
        f"Empirical L3 latency, across 5 seeds × 25 signals = "
        f"{n['n_signals_total']} reconstructions:",
        st["body"]))
    s.append(code(
        f"worst-seed p95   = {n['latency_p95_ms']:>5.0f} ms      "
        f"(vs 2000 ms fast-mode budget)\n"
        f"mean across all  = {n['latency_mean_ms']:>5.1f} ms\n"
        f"latency axis     = {n['latency_axis']:>5.3f}        "
        f"(min(1, budget / worst-seed p95))",
        st))
    s.append(Paragraph(
        "This earns the full 0.150 latency contribution and leaves the "
        "remaining axes as the optimisation surface.", st["body"]))

    # Section 5
    s.append(Paragraph(
        "5. Continuous Learning &amp; Auditability", st["h2"]))
    s.append(bullet(
        "<b>Profile formation.</b> Every new event recomputes the affected "
        "profile's signature; remediation events flip "
        "<font face='Courier'>resolved</font> and append to the historical "
        "ledger.", st))
    s.append(bullet(
        "<b>Feedback persistence.</b> "
        "<font face='Courier'>_feedback</font> stores every remediation "
        "observation with (incident_id, action, target, outcome, "
        "observed_at, canonical_service_id). Future similar incidents "
        "reweight remediation candidates against this ledger.", st))
    s.append(bullet(
        "<b>Reasoning audit.</b> Every match in the returned "
        "<font face='Courier'>Context</font> carries lineage proof, "
        "shape-component scores, sequence audit, behavioural signature "
        "components, remediation history, and confidence contributors. The "
        "same Context flows through to the React workspace, so an operator "
        "inspects exactly what the engine did. This is the substrate the "
        "panel-graded <font face='Courier'>manual_context</font> and "
        "<font face='Courier'>manual_explain</font> axes evaluate.", st))

    # Section 6
    s.append(Paragraph("6. Reproducibility", st["h2"]))
    s.append(Paragraph(
        "Single command, fixed seeds, locked stretch generator, "
        "deterministic adapter:", st["body"]))
    s.append(code(
        "cd bench-p02-context\n"
        "pip install -r requirements.txt\n"
        "python run.py --adapter adapters.memora:Engine --out l3_report.json",
        st))
    s.append(Paragraph(
        f"Adapter source: <font face='Courier'>{n['adapter_path']}</font>. "
        "Rerunning on judges' machines reproduces the per-seed and "
        "aggregated numbers above to the rounding precision shown in "
        "<font face='Courier'>metrics.aggregate</font>.", st["body"]))

    # Section 7
    s.append(Paragraph("7. Honest Assessment", st["h2"]))
    s.append(Paragraph(
        "Latency and remediation transfer behave well at the L3 stretch "
        f"scale (latency at full credit; remediation at "
        f"{n['remediation_acc']*100:.1f}% across 5 action types — well "
        "above the 20% random baseline). Recall and precision are the "
        f"active optimisation surface: the engine currently lands "
        f"recall@5 = {n['recall@5']:.3f} and precision@5_mean = "
        f"{n['precision@5_mean']:.3f} against the L3 stretch (cascading "
        "renames + 20% decoy rate). The alias-graph BFS, shape signature, "
        "and trigger inference are all in place; the next iteration "
        "tightens candidate generation across deeper rename hops and the "
        "decoy-confidence threshold so unmatched signals return empty "
        "rather than confidently wrong. The architecture and the audit "
        "trail do not change — only the ranking calibration does.",
        st["body"]))

    return s


def main():
    n = load_numbers()
    st = build_styles()
    doc = make_doc(OUT)
    doc.build(build_story(n, st))
    size = os.path.getsize(OUT)
    print(f"wrote {OUT}  ({size:,} bytes, "
          f"score {n['weighted_score']:.4f}/{n['max_automated']:.2f})")


if __name__ == "__main__":
    main()
