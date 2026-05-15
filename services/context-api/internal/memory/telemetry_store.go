package memory

import (
	"fmt"
	"slices"
	"strings"
	"sync"

	"github.com/memora/pce/services/context-api/internal/domain"
)

type TelemetryStore struct {
	mu     sync.RWMutex
	events []domain.Event
}

func NewTelemetryStore() *TelemetryStore {
	return &TelemetryStore{}
}

func (s *TelemetryStore) Append(events []domain.Event) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.events = append(s.events, events...)
	slices.SortFunc(s.events, func(a, b domain.Event) int {
		if a.TS.Before(b.TS) {
			return -1
		}
		if a.TS.After(b.TS) {
			return 1
		}
		if a.EventID < b.EventID {
			return -1
		}
		if a.EventID > b.EventID {
			return 1
		}
		return 0
	})

	return nil
}

func (s *TelemetryStore) List(filter domain.RelatedEventFilter) ([]domain.Event, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	allowed := map[string]struct{}{}
	for _, svc := range filter.ServiceNames {
		if svc != "" {
			allowed[svc] = struct{}{}
		}
	}

	var out []domain.Event
	for _, event := range s.events {
		if filter.TenantID != "" && event.TenantID != filter.TenantID {
			continue
		}
		if filter.Environment != "" && event.Environment != filter.Environment {
			continue
		}
		if !filter.From.IsZero() && event.TS.Before(filter.From) {
			continue
		}
		if !filter.To.IsZero() && event.TS.After(filter.To) {
			continue
		}
		if filter.TraceID != "" && event.TraceID != filter.TraceID {
			continue
		}
		if filter.IncidentID != "" && event.IncidentID != "" && event.IncidentID != filter.IncidentID {
			continue
		}
		if len(allowed) > 0 {
			if _, ok := allowed[event.ServiceName]; !ok {
				if _, ok := allowed[event.CanonicalServiceID]; !ok {
					if !matchesRelatedEntity(event, allowed) {
						continue
					}
				}
			}
		}

		out = append(out, event)
	}

	return out, nil
}

func matchesRelatedEntity(event domain.Event, allowed map[string]struct{}) bool {
	for _, entity := range event.Entities {
		if _, ok := allowed[entity]; ok {
			return true
		}
	}

	blob := strings.ToLower(fmt.Sprintf("%v", event.Attributes))
	for service := range allowed {
		if service == "" {
			continue
		}
		if strings.Contains(blob, strings.ToLower(service)) {
			return true
		}
	}

	return false
}
