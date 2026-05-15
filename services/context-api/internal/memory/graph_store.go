package memory

import (
	"slices"
	"strings"
	"sync"

	"github.com/memora/pce/services/context-api/internal/domain"
)

type GraphStore struct {
	mu            sync.RWMutex
	canonical     map[string]string
	adjacency     map[string]map[string]struct{}
	incidentByID  map[string]domain.IncidentMemory
}

func NewGraphStore() *GraphStore {
	return &GraphStore{
		canonical:    map[string]string{},
		adjacency:    map[string]map[string]struct{}{},
		incidentByID: map[string]domain.IncidentMemory{},
	}
}

func (s *GraphStore) Ping() error {
	return nil
}

func (s *GraphStore) UpsertAlias(alias domain.AliasRecord) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	keyFrom := aliasKey(alias.TenantID, alias.Environment, alias.From)
	keyTo := aliasKey(alias.TenantID, alias.Environment, alias.To)

	canonical := alias.CanonicalServiceID
	if canonical == "" {
		canonical = existingCanonical(s.canonical, keyFrom, keyTo)
		if canonical == "" {
			canonical = "svc:" + strings.ToLower(alias.To)
		}
	}

	s.canonical[keyFrom] = canonical
	s.canonical[keyTo] = canonical
	link(s.adjacency, keyFrom, keyTo)
	link(s.adjacency, keyTo, keyFrom)
	for _, key := range connectedKeys(s.adjacency, keyFrom) {
		s.canonical[key] = canonical
	}

	return nil
}

func (s *GraphStore) ResolveCanonical(tenantID, environment, service string) string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if service == "" {
		return ""
	}

	key := aliasKey(tenantID, environment, service)
	if canonical, ok := s.canonical[key]; ok {
		return canonical
	}

	return "svc:" + strings.ToLower(service)
}

func (s *GraphStore) AliasesFor(tenantID, environment, service string) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	start := aliasKey(tenantID, environment, service)
	seen := map[string]struct{}{start: {}}
	queue := []string{start}
	var aliases []string

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		aliases = append(aliases, serviceNameFromKey(current))
		for next := range s.adjacency[current] {
			if _, ok := seen[next]; ok {
				continue
			}
			seen[next] = struct{}{}
			queue = append(queue, next)
		}
	}

	slices.Sort(aliases)
	return slices.Compact(aliases)
}

func (s *GraphStore) StoreIncidentMemory(memory domain.IncidentMemory) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.incidentByID[memory.Signal.IncidentID] = memory
	return nil
}

func (s *GraphStore) GetIncidentMemory(incidentID string) (domain.IncidentMemory, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	memory, ok := s.incidentByID[incidentID]
	return memory, ok
}

func (s *GraphStore) ListIncidentMemories(tenantID, environment string) []domain.IncidentMemory {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var out []domain.IncidentMemory
	for _, memory := range s.incidentByID {
		if memory.Signal.TenantID == tenantID && memory.Signal.Environment == environment {
			out = append(out, memory)
		}
	}

	slices.SortFunc(out, func(a, b domain.IncidentMemory) int {
		if a.Signal.TS.Before(b.Signal.TS) {
			return -1
		}
		if a.Signal.TS.After(b.Signal.TS) {
			return 1
		}
		return strings.Compare(a.Signal.IncidentID, b.Signal.IncidentID)
	})

	return out
}

func existingCanonical(canonical map[string]string, keys ...string) string {
	for _, key := range keys {
		if value, ok := canonical[key]; ok {
			return value
		}
	}
	return ""
}

func aliasKey(tenantID, environment, service string) string {
	return tenantID + "|" + environment + "|" + strings.ToLower(service)
}

func serviceNameFromKey(key string) string {
	parts := strings.SplitN(key, "|", 3)
	if len(parts) != 3 {
		return key
	}
	return parts[2]
}

func link(adjacency map[string]map[string]struct{}, from, to string) {
	if _, ok := adjacency[from]; !ok {
		adjacency[from] = map[string]struct{}{}
	}
	adjacency[from][to] = struct{}{}
}

func connectedKeys(adjacency map[string]map[string]struct{}, start string) []string {
	seen := map[string]struct{}{start: {}}
	queue := []string{start}
	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]
		for next := range adjacency[current] {
			if _, ok := seen[next]; ok {
				continue
			}
			seen[next] = struct{}{}
			queue = append(queue, next)
		}
	}
	out := make([]string, 0, len(seen))
	for key := range seen {
		out = append(out, key)
	}
	return out
}
