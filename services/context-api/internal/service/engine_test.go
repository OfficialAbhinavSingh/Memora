package service

import (
	"testing"
	"time"

	"github.com/memora/pce/services/context-api/internal/app"
	"github.com/memora/pce/services/context-api/internal/domain"
	"github.com/memora/pce/services/context-api/internal/memory"
)

func TestReconstructAcrossRenameAndRollbackHistory(t *testing.T) {
	engine := NewEngine(memory.NewTelemetryStore(), memory.NewGraphStore(), memory.NewFeedbackStore(), app.Config{
		FastWindow:         time.Hour,
		DeepWindow:         6 * time.Hour,
		SimilarityLookback: 365 * 24 * time.Hour,
	})

	base := time.Date(2026, 5, 10, 14, 0, 0, 0, time.UTC)

	err := engine.Ingest([]domain.Event{
		{TS: base.Add(20 * time.Minute), Kind: "topology", TenantID: "t1", Environment: "prod", Attributes: map[string]any{"change": "rename", "from": "payments-svc", "to": "billing-svc"}},
		{TS: base.Add(21 * time.Minute), Kind: "deploy", TenantID: "t1", Environment: "prod", ServiceName: "billing-svc", Attributes: map[string]any{"version": "v2.14.0"}},
		{TS: base.Add(22 * time.Minute), Kind: "metric", TenantID: "t1", Environment: "prod", ServiceName: "billing-svc", Attributes: map[string]any{"name": "latency_p99_ms", "value": float64(4820)}},
		{TS: base.Add(23 * time.Minute), Kind: "log", TenantID: "t1", Environment: "prod", ServiceName: "checkout-api", Attributes: map[string]any{"level": "error", "msg": "timeout calling billing-svc"}},
	})
	if err != nil {
		t.Fatalf("ingest telemetry: %v", err)
	}

	if err := engine.RecordFeedback(domain.FeedbackRequest{
		IncidentID:   "INC-700",
		TenantID:     "t1",
		Environment:  "prod",
		Action:       "rollback",
		Target:       "payments-svc",
		Outcome:      "resolved",
		ObservedAt:   base.Add(10 * time.Minute),
		ServiceName:  "payments-svc",
		AliasService: "svc:billing-svc",
	}); err != nil {
		t.Fatalf("record feedback: %v", err)
	}

	_, err = engine.Reconstruct(domain.ReconstructRequest{
		Signal: domain.IncidentSignal{
			IncidentID:  "INC-700",
			TS:          base.Add(11 * time.Minute),
			TenantID:    "t1",
			Environment: "prod",
			ServiceName: "payments-svc",
			Trigger:     "alert:payments/error-rate",
		},
		Mode: domain.ModeFast,
	})
	if err != nil {
		t.Fatalf("seed reconstruction: %v", err)
	}

	context, err := engine.Reconstruct(domain.ReconstructRequest{
		Signal: domain.IncidentSignal{
			IncidentID:  "INC-714",
			TS:          base.Add(24 * time.Minute),
			TenantID:    "t1",
			Environment: "prod",
			ServiceName: "billing-svc",
			Trigger:     "alert:checkout-api/error-rate>5%",
		},
		Mode: domain.ModeFast,
	})
	if err != nil {
		t.Fatalf("reconstruct: %v", err)
	}

	if len(context.CausalChain) == 0 {
		t.Fatalf("expected causal chain")
	}
	if len(context.SimilarPastIncidents) == 0 || context.SimilarPastIncidents[0].PastIncidentID != "INC-700" {
		t.Fatalf("expected similar incident to include renamed lineage match, got %+v", context.SimilarPastIncidents)
	}
	if len(context.SuggestedRemediations) == 0 || context.SuggestedRemediations[0].Action != "rollback" {
		t.Fatalf("expected rollback suggestion, got %+v", context.SuggestedRemediations)
	}
}

func TestGetIncidentMemory(t *testing.T) {
	engine := NewEngine(memory.NewTelemetryStore(), memory.NewGraphStore(), memory.NewFeedbackStore(), app.Config{
		FastWindow:         time.Hour,
		DeepWindow:         time.Hour,
		SimilarityLookback: 365 * 24 * time.Hour,
	})

	_, err := engine.Reconstruct(domain.ReconstructRequest{
		Signal: domain.IncidentSignal{
			IncidentID:  "INC-1",
			TS:          time.Now().UTC(),
			TenantID:    "t1",
			Environment: "prod",
			ServiceName: "api",
			Trigger:     "alert:test",
		},
		Mode: domain.ModeFast,
	})
	if err != nil {
		t.Fatalf("reconstruct: %v", err)
	}

	memory, ok := engine.GetIncidentMemory("INC-1")
	if !ok {
		t.Fatalf("expected incident memory")
	}
	if memory.Signal.IncidentID != "INC-1" {
		t.Fatalf("unexpected incident id: %s", memory.Signal.IncidentID)
	}
}

func TestChainedRenameSimilarityUsesCanonicalLineage(t *testing.T) {
	engine := NewEngine(memory.NewTelemetryStore(), memory.NewGraphStore(), memory.NewFeedbackStore(), app.Config{
		FastWindow:         2 * time.Hour,
		DeepWindow:         6 * time.Hour,
		SimilarityLookback: 365 * 24 * time.Hour,
	})

	base := time.Date(2026, 5, 10, 10, 0, 0, 0, time.UTC)
	err := engine.Ingest([]domain.Event{
		{TS: base, Kind: "topology", TenantID: "t1", Environment: "prod", Attributes: map[string]any{"change": "rename", "from": "payments-svc", "to": "billing-svc"}},
		{TS: base.Add(time.Minute), Kind: "topology", TenantID: "t1", Environment: "prod", Attributes: map[string]any{"change": "rename", "from": "billing-svc", "to": "ledger-svc"}},
		{TS: base.Add(10 * time.Minute), Kind: "deploy", TenantID: "t1", Environment: "prod", ServiceName: "payments-svc", Attributes: map[string]any{"version": "v1"}},
		{TS: base.Add(11 * time.Minute), Kind: "metric", TenantID: "t1", Environment: "prod", ServiceName: "payments-svc", Attributes: map[string]any{"name": "latency_p99_ms", "value": float64(2200)}},
	})
	if err != nil {
		t.Fatalf("ingest seed: %v", err)
	}

	_, err = engine.Reconstruct(domain.ReconstructRequest{
		Signal: domain.IncidentSignal{IncidentID: "INC-1", TS: base.Add(12 * time.Minute), TenantID: "t1", Environment: "prod", ServiceName: "payments-svc", Trigger: "latency"},
	})
	if err != nil {
		t.Fatalf("seed reconstruct: %v", err)
	}

	if err := engine.Ingest([]domain.Event{
		{TS: base.Add(30 * time.Minute), Kind: "deploy", TenantID: "t1", Environment: "prod", ServiceName: "ledger-svc", Attributes: map[string]any{"version": "v2"}},
		{TS: base.Add(31 * time.Minute), Kind: "metric", TenantID: "t1", Environment: "prod", ServiceName: "ledger-svc", Attributes: map[string]any{"name": "latency_p99_ms", "value": float64(2400)}},
	}); err != nil {
		t.Fatalf("ingest eval: %v", err)
	}

	context, err := engine.Reconstruct(domain.ReconstructRequest{
		Signal: domain.IncidentSignal{IncidentID: "INC-2", TS: base.Add(32 * time.Minute), TenantID: "t1", Environment: "prod", ServiceName: "ledger-svc", Trigger: "latency"},
	})
	if err != nil {
		t.Fatalf("eval reconstruct: %v", err)
	}
	if len(context.SimilarPastIncidents) == 0 || context.SimilarPastIncidents[0].PastIncidentID != "INC-1" {
		t.Fatalf("expected chained rename match, got %+v", context.SimilarPastIncidents)
	}
}

func TestRemediationFeedbackReinforcementAndFailurePenalty(t *testing.T) {
	engine := NewEngine(memory.NewTelemetryStore(), memory.NewGraphStore(), memory.NewFeedbackStore(), app.Config{
		FastWindow:         time.Hour,
		DeepWindow:         time.Hour,
		SimilarityLookback: 365 * 24 * time.Hour,
	})

	base := time.Date(2026, 5, 10, 10, 0, 0, 0, time.UTC)
	if err := engine.RecordFeedback(domain.FeedbackRequest{
		IncidentID: "INC-1", TenantID: "t1", Environment: "prod", Action: "rollback", Target: "api", Outcome: "worked", ObservedAt: base, ServiceName: "api",
	}); err != nil {
		t.Fatalf("record worked: %v", err)
	}
	if err := engine.RecordFeedback(domain.FeedbackRequest{
		IncidentID: "INC-2", TenantID: "t1", Environment: "prod", Action: "restart", Target: "api", Outcome: "failed", ObservedAt: base, ServiceName: "api",
	}); err != nil {
		t.Fatalf("record failed: %v", err)
	}

	context, err := engine.Reconstruct(domain.ReconstructRequest{
		Signal: domain.IncidentSignal{IncidentID: "INC-3", TS: base.Add(time.Hour), TenantID: "t1", Environment: "prod", ServiceName: "api", Trigger: "latency"},
	})
	if err != nil {
		t.Fatalf("reconstruct: %v", err)
	}
	if len(context.SuggestedRemediations) < 2 {
		t.Fatalf("expected at least two suggestions, got %+v", context.SuggestedRemediations)
	}
	if context.SuggestedRemediations[0].Action != "rollback" {
		t.Fatalf("expected worked feedback to outrank failed feedback, got %+v", context.SuggestedRemediations)
	}
}
