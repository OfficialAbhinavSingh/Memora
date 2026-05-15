package postgres

import (
	"context"
	"slices"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/memora/pce/services/context-api/internal/domain"
	"github.com/memora/pce/services/context-api/internal/memory"
)

type GraphStore struct {
	pool         *pgxpool.Pool
	incidentSide *memory.GraphStore
}

type aliasRow struct {
	From      string
	To        string
	Canonical string
}

func NewGraphStore(pool *pgxpool.Pool) *GraphStore {
	return &GraphStore{
		pool:         pool,
		incidentSide: memory.NewGraphStore(),
	}
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
	return s.incidentSide.StoreIncidentMemory(memory)
}

func (s *GraphStore) GetIncidentMemory(incidentID string) (domain.IncidentMemory, bool) {
	return s.incidentSide.GetIncidentMemory(incidentID)
}

func (s *GraphStore) ListIncidentMemories(tenantID, environment string) []domain.IncidentMemory {
	return s.incidentSide.ListIncidentMemories(tenantID, environment)
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
		if canonicalID == "" {
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
