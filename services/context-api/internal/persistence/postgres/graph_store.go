package postgres

import (
	"context"
	"encoding/json"
	"slices"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/memora/pce/services/context-api/internal/domain"
)

type GraphStore struct {
	pool *pgxpool.Pool
}

type aliasRow struct {
	From      string
	To        string
	Canonical string
}

func NewGraphStore(pool *pgxpool.Pool) *GraphStore {
	return &GraphStore{pool: pool}
}

func (s *GraphStore) Ping() error {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	return s.pool.Ping(ctx)
}

func (s *GraphStore) UpsertAlias(alias domain.AliasRecord) error {
	_, err := s.pool.Exec(context.Background(), `
		INSERT INTO topology_aliases
		    (tenant_id, environment, service_from, service_to, canonical_service_id, confidence, observed_at)
		VALUES
		    ($1, $2, $3, $4, $5, $6, $7)
	`,
		alias.TenantID,
		alias.Environment,
		alias.From,
		alias.To,
		alias.CanonicalServiceID,
		alias.Confidence,
		alias.ObservedAt.UTC(),
	)
	return err
}

func (s *GraphStore) ResolveCanonical(tenantID, environment, service string) string {
	if strings.TrimSpace(service) == "" {
		return ""
	}
	rows, err := s.loadAliases(tenantID, environment)
	if err != nil {
		return "svc:" + strings.ToLower(service)
	}
	canonical, _ := aliasGraph(rows, service)
	if canonical == "" {
		return "svc:" + strings.ToLower(service)
	}
	return canonical
}

func (s *GraphStore) AliasesFor(tenantID, environment, service string) []string {
	if strings.TrimSpace(service) == "" {
		return nil
	}
	rows, err := s.loadAliases(tenantID, environment)
	if err != nil {
		return []string{strings.ToLower(service)}
	}
	_, aliases := aliasGraph(rows, service)
	if len(aliases) == 0 {
		return []string{strings.ToLower(service)}
	}
	return aliases
}

func (s *GraphStore) StoreIncidentMemory(memory domain.IncidentMemory) error {
	signal, err := json.Marshal(memory.Signal)
	if err != nil {
		return err
	}
	contextPayload, err := json.Marshal(memory.Context)
	if err != nil {
		return err
	}
	observedAt := memory.Signal.TS
	if observedAt.IsZero() {
		observedAt = time.Now().UTC()
	}

	_, err = s.pool.Exec(context.Background(), `
		INSERT INTO incident_memories
		    (tenant_id, environment, incident_id, signal, context, observed_at, updated_at)
		VALUES
		    ($1, $2, $3, $4, $5, $6, NOW())
		ON CONFLICT (incident_id)
		DO UPDATE SET
		    tenant_id = EXCLUDED.tenant_id,
		    environment = EXCLUDED.environment,
		    signal = EXCLUDED.signal,
		    context = EXCLUDED.context,
		    observed_at = EXCLUDED.observed_at,
		    updated_at = NOW()
	`,
		memory.Signal.TenantID,
		memory.Signal.Environment,
		memory.Signal.IncidentID,
		string(signal),
		string(contextPayload),
		observedAt.UTC(),
	)
	return err
}

func (s *GraphStore) GetIncidentMemory(incidentID string) (domain.IncidentMemory, bool) {
	var signalPayload, contextPayload []byte
	err := s.pool.QueryRow(context.Background(), `
		SELECT signal, context
		FROM incident_memories
		WHERE incident_id = $1
	`, incidentID).Scan(&signalPayload, &contextPayload)
	if err != nil {
		return domain.IncidentMemory{}, false
	}

	memory, err := decodeIncidentMemory(signalPayload, contextPayload)
	if err != nil {
		return domain.IncidentMemory{}, false
	}
	return memory, true
}

func (s *GraphStore) ListIncidentMemories(tenantID, environment string) []domain.IncidentMemory {
	rows, err := s.pool.Query(context.Background(), `
		SELECT signal, context
		FROM incident_memories
		WHERE tenant_id = $1 AND environment = $2
		ORDER BY observed_at ASC, incident_id ASC
	`, tenantID, environment)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var out []domain.IncidentMemory
	for rows.Next() {
		var signalPayload, contextPayload []byte
		if err := rows.Scan(&signalPayload, &contextPayload); err != nil {
			return out
		}
		memory, err := decodeIncidentMemory(signalPayload, contextPayload)
		if err != nil {
			continue
		}
		out = append(out, memory)
	}
	return out
}

func decodeIncidentMemory(signalPayload, contextPayload []byte) (domain.IncidentMemory, error) {
	var memory domain.IncidentMemory
	if err := json.Unmarshal(signalPayload, &memory.Signal); err != nil {
		return memory, err
	}
	if err := json.Unmarshal(contextPayload, &memory.Context); err != nil {
		return memory, err
	}
	return memory, nil
}

func (s *GraphStore) loadAliases(tenantID, environment string) ([]aliasRow, error) {
	rows, err := s.pool.Query(context.Background(), `
		SELECT service_from, service_to, canonical_service_id
		FROM topology_aliases
		WHERE tenant_id = $1 AND environment = $2
		ORDER BY observed_at ASC
	`, tenantID, environment)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []aliasRow
	for rows.Next() {
		var row aliasRow
		if err := rows.Scan(&row.From, &row.To, &row.Canonical); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func aliasGraph(rows []aliasRow, service string) (string, []string) {
	adjacency := map[string]map[string]struct{}{}
	canonical := map[string]string{}

	for _, row := range rows {
		from := strings.ToLower(row.From)
		to := strings.ToLower(row.To)
		if _, ok := adjacency[from]; !ok {
			adjacency[from] = map[string]struct{}{}
		}
		if _, ok := adjacency[to]; !ok {
			adjacency[to] = map[string]struct{}{}
		}
		adjacency[from][to] = struct{}{}
		adjacency[to][from] = struct{}{}
		if row.Canonical != "" {
			canonical[from] = row.Canonical
			canonical[to] = row.Canonical
		}
	}

	start := strings.ToLower(service)
	seen := map[string]struct{}{start: {}}
	queue := []string{start}
	aliases := []string{}
	canonicalID := canonical[start]

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		aliases = append(aliases, current)
		if canonical[current] != "" {
			canonicalID = canonical[current]
		}
		for next := range adjacency[current] {
			if _, ok := seen[next]; ok {
				continue
			}
			seen[next] = struct{}{}
			queue = append(queue, next)
		}
	}

	slices.Sort(aliases)
	aliases = slices.Compact(aliases)
	if canonicalID == "" {
		canonicalID = "svc:" + start
	}
	return canonicalID, aliases
}
