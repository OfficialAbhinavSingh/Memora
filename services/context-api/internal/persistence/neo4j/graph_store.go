package neo4j

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/memora/pce/services/context-api/internal/domain"
	"github.com/memora/pce/services/context-api/internal/memory"
)

type GraphStore struct {
	baseURL  string
	user     string
	password string
	client   *http.Client
	side     *memory.GraphStore
}

func NewGraphStore(baseURL, user, password string) *GraphStore {
	return &GraphStore{
		baseURL:  strings.TrimRight(baseURL, "/"),
		user:     user,
		password: password,
		client:   &http.Client{Timeout: 5 * time.Second},
		side:     memory.NewGraphStore(),
	}
}

func (s *GraphStore) Ping() error {
	return s.exec(context.Background(), "RETURN 1", nil)
}

func (s *GraphStore) UpsertAlias(alias domain.AliasRecord) error {
	if err := s.side.UpsertAlias(alias); err != nil {
		return err
	}
	return s.exec(context.Background(), `
		MERGE (from:Service {tenant_id: $tenant_id, environment: $environment, name: $from})
		MERGE (to:Service {tenant_id: $tenant_id, environment: $environment, name: $to})
		SET from.canonical_service_id = $canonical_service_id,
		    to.canonical_service_id = $canonical_service_id
		MERGE (from)-[r:ALIASED_TO]->(to)
		SET r.confidence = $confidence, r.observed_at = $observed_at
	`, map[string]any{
		"tenant_id":            alias.TenantID,
		"environment":          alias.Environment,
		"from":                 alias.From,
		"to":                   alias.To,
		"canonical_service_id": alias.CanonicalServiceID,
		"confidence":           alias.Confidence,
		"observed_at":          alias.ObservedAt.UTC().Format(time.RFC3339Nano),
	})
}

func (s *GraphStore) ResolveCanonical(tenantID, environment, service string) string {
	return s.side.ResolveCanonical(tenantID, environment, service)
}

func (s *GraphStore) AliasesFor(tenantID, environment, service string) []string {
	return s.side.AliasesFor(tenantID, environment, service)
}

func (s *GraphStore) StoreIncidentMemory(memory domain.IncidentMemory) error {
	if err := s.side.StoreIncidentMemory(memory); err != nil {
		return err
	}
	contextPayload, _ := json.Marshal(memory.Context)
	if err := s.exec(context.Background(), `
		MERGE (i:Incident {incident_id: $incident_id})
		SET i.tenant_id = $tenant_id,
		    i.environment = $environment,
		    i.service_name = $service_name,
		    i.canonical_service_id = $canonical_service_id,
		    i.trigger = $trigger,
		    i.context = $context,
		    i.observed_at = $observed_at
	`, map[string]any{
		"incident_id":          memory.Signal.IncidentID,
		"tenant_id":            memory.Signal.TenantID,
		"environment":          memory.Signal.Environment,
		"service_name":         memory.Signal.ServiceName,
		"canonical_service_id": memory.Signal.CanonicalServiceID,
		"trigger":              memory.Signal.Trigger,
		"context":              string(contextPayload),
		"observed_at":          memory.Signal.TS.UTC().Format(time.RFC3339Nano),
	}); err != nil {
		return err
	}
	for _, match := range memory.Context.SimilarPastIncidents {
		_ = s.exec(context.Background(), `
			MERGE (i:Incident {incident_id: $incident_id})
			MERGE (p:Incident {incident_id: $past_incident_id})
			MERGE (i)-[r:SIMILAR_TO]->(p)
			SET r.similarity = $similarity, r.rationale = $rationale
		`, map[string]any{
			"incident_id":      memory.Signal.IncidentID,
			"past_incident_id": match.PastIncidentID,
			"similarity":       match.Similarity,
			"rationale":        match.Rationale,
		})
	}
	for _, edge := range memory.Context.CausalChain {
		_ = s.exec(context.Background(), `
			MERGE (cause:Event {event_id: $cause_id})
			MERGE (effect:Event {event_id: $effect_id})
			MERGE (cause)-[r:CAUSES]->(effect)
			SET r.confidence = $confidence, r.evidence = $evidence
		`, map[string]any{
			"cause_id":    edge.CauseID,
			"effect_id":   edge.EffectID,
			"confidence":  edge.Confidence,
			"evidence":    strings.Join(edge.Evidence, ","),
		})
	}
	for _, remediation := range memory.Context.SuggestedRemediations {
		_ = s.exec(context.Background(), `
			MERGE (i:Incident {incident_id: $incident_id})
			MERGE (r:Remediation {action: $action, target: $target})
			MERGE (i)-[rel:SUGGESTS]->(r)
			SET rel.confidence = $confidence, rel.historical_outcome = $historical_outcome
		`, map[string]any{
			"incident_id":         memory.Signal.IncidentID,
			"action":              remediation.Action,
			"target":              remediation.Target,
			"confidence":          remediation.Confidence,
			"historical_outcome":  remediation.HistoricalOutcome,
		})
	}
	return nil
}

func (s *GraphStore) GetIncidentMemory(incidentID string) (domain.IncidentMemory, bool) {
	return s.side.GetIncidentMemory(incidentID)
}

func (s *GraphStore) ListIncidentMemories(tenantID, environment string) []domain.IncidentMemory {
	return s.side.ListIncidentMemories(tenantID, environment)
}

func (s *GraphStore) exec(ctx context.Context, statement string, params map[string]any) error {
	body, err := json.Marshal(map[string]any{
		"statements": []map[string]any{{
			"statement":  statement,
			"parameters": params,
		}},
	})
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.baseURL+"/db/neo4j/tx/commit", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	if s.user != "" || s.password != "" {
		req.SetBasicAuth(s.user, s.password)
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return fmt.Errorf("neo4j query failed: %s", resp.Status)
	}
	return nil
}
