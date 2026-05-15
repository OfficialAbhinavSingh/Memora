package service

import (
	"crypto/sha1"
	"encoding/hex"
	"errors"
	"fmt"
	"math"
	"slices"
	"strings"
	"time"

	"github.com/memora/pce/services/context-api/internal/app"
	"github.com/memora/pce/services/context-api/internal/domain"
	"github.com/memora/pce/services/context-api/internal/store"
)

type Engine struct {
	telemetry store.TelemetryStore
	graph     store.GraphStore
	feedback  store.FeedbackStore
	cfg       app.Config
}

var ErrInvalidInput = errors.New("invalid input")

func IsInvalidInput(err error) bool {
	return errors.Is(err, ErrInvalidInput)
}

func NewEngine(telemetry store.TelemetryStore, graph store.GraphStore, feedback store.FeedbackStore, cfg app.Config) *Engine {
	return &Engine{
		telemetry: telemetry,
		graph:     graph,
		feedback:  feedback,
		cfg:       cfg,
	}
}

func (e *Engine) Ingest(events []domain.Event) error {
	if len(events) == 0 {
		return invalidInput("events is required")
	}

	normalized := make([]domain.Event, 0, len(events))
	for _, event := range events {
		if strings.TrimSpace(event.Kind) == "" {
			return invalidInput("event.kind is required")
		}
		if strings.TrimSpace(event.TenantID) == "" {
			return invalidInput("event.tenant_id is required")
		}
		if strings.TrimSpace(event.Environment) == "" {
			return invalidInput("event.environment is required")
		}

		normalizedEvent := e.normalize(event)
		normalized = append(normalized, normalizedEvent)
		if normalizedEvent.Kind == "topology" {
			from, _ := stringAttr(normalizedEvent.Attributes, "from")
			to, _ := stringAttr(normalizedEvent.Attributes, "to")
			change, _ := stringAttr(normalizedEvent.Attributes, "change")
			if change == "rename" && from != "" && to != "" {
				_ = e.graph.UpsertAlias(domain.AliasRecord{
					TenantID:           normalizedEvent.TenantID,
					Environment:        normalizedEvent.Environment,
					From:               from,
					To:                 to,
					CanonicalServiceID: "svc:" + strings.ToLower(to),
					Confidence:         1.0,
					ObservedAt:         normalizedEvent.TS,
				})
			}
		}
	}

	return e.telemetry.Append(normalized)
}

func (e *Engine) Reconstruct(req domain.ReconstructRequest) (domain.Context, error) {
	mode := req.Mode
	if mode == "" {
		mode = domain.ModeFast
	}
	if mode != domain.ModeFast && mode != domain.ModeDeep {
		return domain.Context{}, invalidInput("mode must be fast or deep")
	}

	signal := req.Signal
	if strings.TrimSpace(signal.IncidentID) == "" {
		return domain.Context{}, invalidInput("signal.incident_id is required")
	}
	if strings.TrimSpace(signal.TenantID) == "" {
		return domain.Context{}, invalidInput("signal.tenant_id is required")
	}
	if strings.TrimSpace(signal.Environment) == "" {
		return domain.Context{}, invalidInput("signal.environment is required")
	}
	if strings.TrimSpace(signal.Trigger) == "" {
		return domain.Context{}, invalidInput("signal.trigger is required")
	}

	if signal.TS.IsZero() {
		signal.TS = time.Now().UTC()
	}
	if signal.CanonicalServiceID == "" && signal.ServiceName != "" {
		signal.CanonicalServiceID = e.graph.ResolveCanonical(signal.TenantID, signal.Environment, signal.ServiceName)
	}

	services := []string{signal.ServiceName, signal.CanonicalServiceID}
	services = append(services, e.graph.AliasesFor(signal.TenantID, signal.Environment, signal.ServiceName)...)
	services = slices.Compact(compactNonEmpty(services))

	window := e.cfg.FastWindow
	if mode == domain.ModeDeep {
		window = e.cfg.DeepWindow
	}

	events, err := e.telemetry.List(domain.RelatedEventFilter{
		TenantID:     signal.TenantID,
		Environment:  signal.Environment,
		ServiceNames: services,
		IncidentID:   signal.IncidentID,
		From:         signal.TS.Add(-window),
		To:           signal.TS.Add(10 * time.Minute),
	})
	if err != nil {
		return domain.Context{}, err
	}

	related := e.rankRelatedEvents(signal, events)
	causal := e.buildCausalChain(signal, related)
	similar := e.findSimilarIncidents(signal, related)
	remediations := e.rankRemediations(signal, similar)
	confidence := e.scoreConfidence(related, causal, similar, remediations)

	context := domain.Context{
		RelatedEvents:         related,
		CausalChain:           causal,
		SimilarPastIncidents:  similar,
		SuggestedRemediations: remediations,
		Confidence:            confidence,
		Explain:               e.explain(signal, related, similar, remediations),
	}

	_ = e.graph.StoreIncidentMemory(domain.IncidentMemory{
		Signal:  signal,
		Context: context,
	})

	return context, nil
}

func (e *Engine) GetIncidentMemory(incidentID string) (domain.IncidentMemory, bool) {
	return e.graph.GetIncidentMemory(incidentID)
}

func (e *Engine) Ready() error {
	for name, dependency := range map[string]any{
		"telemetry": e.telemetry,
		"graph":     e.graph,
		"feedback":  e.feedback,
	} {
		checker, ok := dependency.(interface{ Ping() error })
		if !ok {
			continue
		}
		if err := checker.Ping(); err != nil {
			return fmt.Errorf("%s store unavailable: %w", name, err)
		}
	}
	return nil
}

func (e *Engine) RecordFeedback(req domain.FeedbackRequest) error {
	if strings.TrimSpace(req.IncidentID) == "" {
		return invalidInput("incident_id is required")
	}
	if strings.TrimSpace(req.TenantID) == "" {
		return invalidInput("tenant_id is required")
	}
	if strings.TrimSpace(req.Environment) == "" {
		return invalidInput("environment is required")
	}
	if strings.TrimSpace(req.Action) == "" {
		return invalidInput("action is required")
	}
	if strings.TrimSpace(req.Target) == "" {
		return invalidInput("target is required")
	}
	if strings.TrimSpace(req.Outcome) == "" {
		return invalidInput("outcome is required")
	}

	service := req.ServiceName
	canonical := req.AliasService
	if canonical == "" && service != "" {
		canonical = e.graph.ResolveCanonical(req.TenantID, req.Environment, service)
	}

	return e.feedback.Record(domain.RemediationRecord{
		IncidentID:         req.IncidentID,
		TenantID:           req.TenantID,
		Environment:        req.Environment,
		Action:             req.Action,
		Target:             req.Target,
		Outcome:            req.Outcome,
		Version:            req.Version,
		ObservedAt:         req.ObservedAt,
		ServiceName:        service,
		CanonicalServiceID: canonical,
	})
}

func (e *Engine) UpsertAlias(req domain.AliasRequest) error {
	if strings.TrimSpace(req.TenantID) == "" {
		return invalidInput("tenant_id is required")
	}
	if strings.TrimSpace(req.Environment) == "" {
		return invalidInput("environment is required")
	}
	if strings.TrimSpace(req.From) == "" {
		return invalidInput("from is required")
	}
	if strings.TrimSpace(req.To) == "" {
		return invalidInput("to is required")
	}
	if req.ObservedAt.IsZero() {
		req.ObservedAt = time.Now().UTC()
	}

	return e.graph.UpsertAlias(domain.AliasRecord{
		TenantID:           req.TenantID,
		Environment:        req.Environment,
		From:               req.From,
		To:                 req.To,
		CanonicalServiceID: "svc:" + strings.ToLower(req.To),
		Confidence:         clampConfidence(req.Confidence),
		ObservedAt:         req.ObservedAt,
	})
}

func invalidInput(message string) error {
	return fmt.Errorf("%w: %s", ErrInvalidInput, message)
}

func (e *Engine) normalize(event domain.Event) domain.Event {
	if event.TS.IsZero() {
		event.TS = time.Now().UTC()
	}
	if event.EventID == "" {
		event.EventID = stableID(event)
	}
	if event.Attributes == nil {
		event.Attributes = map[string]any{}
	}
	if event.Provenance == nil {
		event.Provenance = map[string]any{"source": "api"}
	}
	if event.CanonicalServiceID == "" && event.ServiceName != "" {
		event.CanonicalServiceID = e.graph.ResolveCanonical(event.TenantID, event.Environment, event.ServiceName)
	}
	if event.Kind == "incident_signal" && event.IncidentID == "" {
		if incidentID, ok := stringAttr(event.Attributes, "incident_id"); ok {
			event.IncidentID = incidentID
		}
	}
	return event
}

func stableID(event domain.Event) string {
	hash := sha1.Sum([]byte(fmt.Sprintf("%s|%s|%s|%s|%s", event.TenantID, event.Environment, event.Kind, event.ServiceName, event.TS.UTC().Format(time.RFC3339Nano))))
	return hex.EncodeToString(hash[:])
}

func (e *Engine) rankRelatedEvents(signal domain.IncidentSignal, events []domain.Event) []domain.Event {
	type scored struct {
		event  domain.Event
		score  float64
		delta  time.Duration
	}

	var scoredEvents []scored
	for _, event := range events {
		score := 0.0
		if event.CanonicalServiceID != "" && event.CanonicalServiceID == signal.CanonicalServiceID {
			score += 0.35
		}
		if event.ServiceName != "" && strings.EqualFold(event.ServiceName, signal.ServiceName) {
			score += 0.20
		}
		if event.IncidentID != "" && event.IncidentID == signal.IncidentID {
			score += 0.20
		}
		if strings.Contains(strings.ToLower(fmt.Sprintf("%v", event.Attributes)), strings.ToLower(signal.Trigger)) {
			score += 0.10
		}
		switch event.Kind {
		case "deploy":
			score += 0.15
		case "metric":
			score += 0.15
		case "log":
			score += 0.12
		case "trace":
			score += 0.12
		case "remediation":
			score += 0.08
		}

		delta := signal.TS.Sub(event.TS)
		if delta < 0 {
			delta = -delta
		}
		score += math.Max(0, 0.18-(delta.Minutes()/180.0))
		scoredEvents = append(scoredEvents, scored{event: event, score: score, delta: delta})
	}

	slices.SortFunc(scoredEvents, func(a, b scored) int {
		if a.score > b.score {
			return -1
		}
		if a.score < b.score {
			return 1
		}
		if a.delta < b.delta {
			return -1
		}
		if a.delta > b.delta {
			return 1
		}
		return strings.Compare(a.event.EventID, b.event.EventID)
	})

	seen := map[string]struct{}{}
	var related []domain.Event
	for _, candidate := range scoredEvents {
		if candidate.score < 0.2 {
			continue
		}
		if _, ok := seen[candidate.event.EventID]; ok {
			continue
		}
		seen[candidate.event.EventID] = struct{}{}
		related = append(related, candidate.event)
		if len(related) == 12 {
			break
		}
	}

	slices.SortFunc(related, func(a, b domain.Event) int {
		if a.TS.Before(b.TS) {
			return -1
		}
		if a.TS.After(b.TS) {
			return 1
		}
		return strings.Compare(a.EventID, b.EventID)
	})

	return related
}

func (e *Engine) buildCausalChain(signal domain.IncidentSignal, events []domain.Event) []domain.CausalEdge {
	var deploys, anomalies, upstreamFailures []domain.Event
	for _, event := range events {
		switch event.Kind {
		case "deploy":
			deploys = append(deploys, event)
		case "metric":
			if metricSpike(event) {
				anomalies = append(anomalies, event)
			}
		case "log":
			if logImpliesFailure(event) {
				upstreamFailures = append(upstreamFailures, event)
			}
		case "trace":
			if traceImpliesLatency(event) {
				upstreamFailures = append(upstreamFailures, event)
			}
		}
	}

	var edges []domain.CausalEdge
	for _, deploy := range deploys {
		for _, anomaly := range anomalies {
			if deploy.TS.Before(anomaly.TS) {
				edges = append(edges, domain.CausalEdge{
					CauseID:    deploy.EventID,
					EffectID:   anomaly.EventID,
					Evidence:   []string{"deploy_precedes_metric_spike"},
					Confidence: 0.72,
				})
			}
		}
	}
	for _, anomaly := range anomalies {
		for _, failure := range upstreamFailures {
			if anomaly.TS.Before(failure.TS) {
				edges = append(edges, domain.CausalEdge{
					CauseID:    anomaly.EventID,
					EffectID:   failure.EventID,
					Evidence:   []string{"metric_or_trace_precedes_upstream_failure"},
					Confidence: 0.68,
				})
			}
		}
	}

	slices.SortFunc(edges, func(a, b domain.CausalEdge) int {
		if a.Confidence > b.Confidence {
			return -1
		}
		if a.Confidence < b.Confidence {
			return 1
		}
		return strings.Compare(a.CauseID+a.EffectID, b.CauseID+b.EffectID)
	})

	if len(edges) > 8 {
		edges = edges[:8]
	}
	return edges
}

func (e *Engine) findSimilarIncidents(signal domain.IncidentSignal, related []domain.Event) []domain.IncidentMatch {
	memories := e.graph.ListIncidentMemories(signal.TenantID, signal.Environment)
	currentSignature := incidentSignature(signal, related)
	var matches []domain.IncidentMatch

	for _, memory := range memories {
		if memory.Signal.IncidentID == signal.IncidentID {
			continue
		}
		if memory.Signal.TS.Before(signal.TS.Add(-e.cfg.SimilarityLookback)) {
			continue
		}
		score := similarityScore(signal, currentSignature, memory.Signal, memory.Context.RelatedEvents)
		if score < 0.35 {
			continue
		}
		rationale := "matched on canonical service lineage, trigger shape, and recent event progression"
		if memory.Signal.CanonicalServiceID != "" && memory.Signal.CanonicalServiceID == signal.CanonicalServiceID {
			rationale = "matched on canonical service lineage and incident progression"
		}
		matches = append(matches, domain.IncidentMatch{
			PastIncidentID: memory.Signal.IncidentID,
			Similarity:     score,
			Rationale:      rationale,
		})
	}

	slices.SortFunc(matches, func(a, b domain.IncidentMatch) int {
		if a.Similarity > b.Similarity {
			return -1
		}
		if a.Similarity < b.Similarity {
			return 1
		}
		return strings.Compare(a.PastIncidentID, b.PastIncidentID)
	})

	if len(matches) > 5 {
		matches = matches[:5]
	}
	return matches
}

func (e *Engine) rankRemediations(signal domain.IncidentSignal, similar []domain.IncidentMatch) []domain.Remediation {
	history := e.feedback.List(signal.TenantID, signal.Environment)
	type candidate struct {
		domain.Remediation
		score float64
	}

	similarSet := map[string]struct{}{}
	for _, match := range similar {
		similarSet[match.PastIncidentID] = struct{}{}
	}
	aliasSet := map[string]struct{}{}
	for _, alias := range e.graph.AliasesFor(signal.TenantID, signal.Environment, signal.ServiceName) {
		aliasSet[strings.ToLower(alias)] = struct{}{}
	}

	grouped := map[string]candidate{}
	for _, record := range history {
		score := 0.2
		if record.CanonicalServiceID != "" && record.CanonicalServiceID == signal.CanonicalServiceID {
			score += 0.35
		} else if _, ok := aliasSet[strings.ToLower(record.Target)]; ok && record.Target != "" {
			score += 0.35
		} else if _, ok := aliasSet[strings.ToLower(record.ServiceName)]; ok && record.ServiceName != "" {
			score += 0.25
		}
		if _, ok := similarSet[record.IncidentID]; ok {
			score += 0.30
		}
		switch strings.ToLower(record.Outcome) {
		case "resolved", "success", "worked":
			score += 0.15
		case "failed":
			score -= 0.15
		}
		if record.Target == signal.ServiceName {
			score += 0.10
		}
		if !record.ObservedAt.IsZero() && !signal.TS.IsZero() && signal.TS.After(record.ObservedAt) {
			ageDays := signal.TS.Sub(record.ObservedAt).Hours() / 24
			score *= math.Max(0.55, 1-(ageDays/365.0)*0.25)
		}

		target := chooseTarget(record, signal, aliasSet)
		key := record.Action + "|" + target
		existing, ok := grouped[key]
		if !ok || score > existing.score {
			grouped[key] = candidate{
				Remediation: domain.Remediation{
					Action:            record.Action,
					Target:            target,
					HistoricalOutcome: record.Outcome,
					Confidence:        clampConfidence(score),
				},
				score: score,
			}
		}
	}

	var suggestions []candidate
	for _, item := range grouped {
		suggestions = append(suggestions, item)
	}

	slices.SortFunc(suggestions, func(a, b candidate) int {
		if a.score > b.score {
			return -1
		}
		if a.score < b.score {
			return 1
		}
		return strings.Compare(a.Action+a.Target, b.Action+b.Target)
	})

	if len(suggestions) == 0 && signal.ServiceName != "" {
		suggestions = append(suggestions, candidate{
			Remediation: domain.Remediation{
				Action:            "inspect_recent_deploy_or_rollback",
				Target:            signal.ServiceName,
				HistoricalOutcome: "unknown",
				Confidence:        0.25,
			},
			score: 0.25,
		})
	}

	var out []domain.Remediation
	for _, item := range suggestions {
		out = append(out, item.Remediation)
		if len(out) == 3 {
			break
		}
	}
	return out
}

func (e *Engine) scoreConfidence(related []domain.Event, causal []domain.CausalEdge, similar []domain.IncidentMatch, remediations []domain.Remediation) float64 {
	score := 0.15
	score += math.Min(0.30, float64(len(related))*0.03)
	score += math.Min(0.25, float64(len(causal))*0.08)
	score += math.Min(0.20, float64(len(similar))*0.06)
	score += math.Min(0.10, float64(len(remediations))*0.04)
	return clampConfidence(score)
}

func (e *Engine) explain(signal domain.IncidentSignal, related []domain.Event, similar []domain.IncidentMatch, remediations []domain.Remediation) string {
	parts := []string{
		fmt.Sprintf("Incident %s was reconstructed using %d related events", signal.IncidentID, len(related)),
	}

	if signal.ServiceName != "" {
		parts = append(parts, fmt.Sprintf("for service lineage rooted at %s", signal.ServiceName))
	}
	if len(similar) > 0 {
		parts = append(parts, fmt.Sprintf("%d historically similar incidents were matched", len(similar)))
	}
	if len(remediations) > 0 {
		parts = append(parts, fmt.Sprintf("top remediation is %s on %s", remediations[0].Action, remediations[0].Target))
	}

	return strings.Join(parts, "; ") + "."
}

func metricSpike(event domain.Event) bool {
	value, ok := numericAttr(event.Attributes, "value")
	return ok && value >= 1000
}

func logImpliesFailure(event domain.Event) bool {
	message := strings.ToLower(stringify(event.Attributes["msg"]))
	level := strings.ToLower(stringify(event.Attributes["level"]))
	return strings.Contains(message, "timeout") || strings.Contains(message, "error") || level == "error"
}

func traceImpliesLatency(event domain.Event) bool {
	value := strings.ToLower(fmt.Sprintf("%v", event.Attributes))
	return strings.Contains(value, "dur_ms") || strings.Contains(value, "latency")
}

func incidentSignature(signal domain.IncidentSignal, related []domain.Event) string {
	kinds := make([]string, 0, len(related))
	tokens := shapeTokens(related)
	for _, event := range related {
		kinds = append(kinds, event.Kind)
	}
	slices.Sort(kinds)
	slices.Sort(tokens)
	return strings.Join(append([]string{signal.Trigger, signal.CanonicalServiceID}, append(kinds, tokens...)...), "|")
}

func similarityScore(signal domain.IncidentSignal, currentSig string, historical domain.IncidentSignal, related []domain.Event) float64 {
	score := 0.0
	if signal.CanonicalServiceID != "" && signal.CanonicalServiceID == historical.CanonicalServiceID {
		score += 0.35
	}
	if strings.EqualFold(signal.Trigger, historical.Trigger) {
		score += 0.25
	}
	if strings.Contains(currentSig, historical.CanonicalServiceID) {
		score += 0.10
	}

	kindSet := map[string]struct{}{}
	for _, event := range related {
		kindSet[event.Kind] = struct{}{}
	}
	if len(kindSet) >= 3 {
		score += 0.15
	}
	if signal.ServiceName != "" && strings.EqualFold(signal.ServiceName, historical.ServiceName) {
		score += 0.15
	}
	sharedShape := 0
	for _, token := range shapeTokens(related) {
		if strings.Contains(currentSig, token) {
			sharedShape++
		}
	}
	score += math.Min(0.25, float64(sharedShape)*0.06)
	return clampConfidence(score)
}

func shapeTokens(events []domain.Event) []string {
	tokens := map[string]struct{}{}
	var deployTS time.Time
	for _, event := range events {
		switch event.Kind {
		case "deploy":
			tokens["deploy"] = struct{}{}
			if deployTS.IsZero() || event.TS.Before(deployTS) {
				deployTS = event.TS
			}
		case "metric":
			name := strings.ToLower(stringify(event.Attributes["name"]))
			if strings.Contains(name, "latency") || metricSpike(event) {
				tokens["latency-spike"] = struct{}{}
			}
			if strings.Contains(name, "error") {
				tokens["error-rate"] = struct{}{}
			}
		case "log":
			if logImpliesFailure(event) {
				tokens["upstream-failure"] = struct{}{}
			}
		case "trace":
			if traceImpliesLatency(event) {
				tokens["trace-latency"] = struct{}{}
			}
		case "remediation":
			action := strings.ToLower(stringify(event.Attributes["action"]))
			outcome := strings.ToLower(stringify(event.Attributes["outcome"]))
			if action != "" {
				tokens["remediation:"+action] = struct{}{}
			}
			if outcome != "" {
				tokens["outcome:"+outcome] = struct{}{}
			}
		}
		if !deployTS.IsZero() && event.TS.After(deployTS) && event.TS.Sub(deployTS) <= 10*time.Minute {
			tokens["post-deploy-window"] = struct{}{}
		}
	}
	out := make([]string, 0, len(tokens))
	for token := range tokens {
		out = append(out, token)
	}
	return out
}

func compactNonEmpty(items []string) []string {
	out := items[:0]
	for _, item := range items {
		if strings.TrimSpace(item) != "" {
			out = append(out, item)
		}
	}
	return out
}

func chooseTarget(record domain.RemediationRecord, signal domain.IncidentSignal, aliases map[string]struct{}) string {
	if record.CanonicalServiceID != "" && record.CanonicalServiceID == signal.CanonicalServiceID && signal.ServiceName != "" {
		return signal.ServiceName
	}
	if _, ok := aliases[strings.ToLower(record.Target)]; ok && signal.ServiceName != "" {
		return signal.ServiceName
	}
	if record.Target != "" {
		return record.Target
	}
	return signal.ServiceName
}

func stringify(value any) string {
	if value == nil {
		return ""
	}
	return fmt.Sprintf("%v", value)
}

func stringAttr(attributes map[string]any, key string) (string, bool) {
	if attributes == nil {
		return "", false
	}
	value, ok := attributes[key]
	if !ok || value == nil {
		return "", false
	}
	return fmt.Sprintf("%v", value), true
}

func numericAttr(attributes map[string]any, key string) (float64, bool) {
	if attributes == nil {
		return 0, false
	}
	value, ok := attributes[key]
	if !ok {
		return 0, false
	}
	switch typed := value.(type) {
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case float64:
		return typed, true
	case float32:
		return float64(typed), true
	default:
		return 0, false
	}
}

func clampConfidence(value float64) float64 {
	if value < 0 {
		return 0
	}
	if value > 1 {
		return 1
	}
	return math.Round(value*100) / 100
}
