package store

import "github.com/memora/pce/services/context-api/internal/domain"

type TelemetryStore interface {
	Append(events []domain.Event) error
	List(filter domain.RelatedEventFilter) ([]domain.Event, error)
}

type GraphStore interface {
	UpsertAlias(alias domain.AliasRecord) error
	ResolveCanonical(tenantID, environment, service string) string
	AliasesFor(tenantID, environment, service string) []string
	StoreIncidentMemory(memory domain.IncidentMemory) error
	GetIncidentMemory(incidentID string) (domain.IncidentMemory, bool)
	ListIncidentMemories(tenantID, environment string) []domain.IncidentMemory
}

type FeedbackStore interface {
	Record(remediation domain.RemediationRecord) error
	List(tenantID, environment string) []domain.RemediationRecord
}

type MirroredGraphStore struct {
	primary GraphStore
	mirrors []GraphStore
}

func NewMirroredGraphStore(primary GraphStore, mirrors ...GraphStore) *MirroredGraphStore {
	return &MirroredGraphStore{primary: primary, mirrors: mirrors}
}

func (s *MirroredGraphStore) UpsertAlias(alias domain.AliasRecord) error {
	if err := s.primary.UpsertAlias(alias); err != nil {
		return err
	}
	for _, mirror := range s.mirrors {
		_ = mirror.UpsertAlias(alias)
	}
	return nil
}

func (s *MirroredGraphStore) ResolveCanonical(tenantID, environment, service string) string {
	return s.primary.ResolveCanonical(tenantID, environment, service)
}

func (s *MirroredGraphStore) AliasesFor(tenantID, environment, service string) []string {
	return s.primary.AliasesFor(tenantID, environment, service)
}

func (s *MirroredGraphStore) StoreIncidentMemory(memory domain.IncidentMemory) error {
	if err := s.primary.StoreIncidentMemory(memory); err != nil {
		return err
	}
	for _, mirror := range s.mirrors {
		_ = mirror.StoreIncidentMemory(memory)
	}
	return nil
}

func (s *MirroredGraphStore) GetIncidentMemory(incidentID string) (domain.IncidentMemory, bool) {
	return s.primary.GetIncidentMemory(incidentID)
}

func (s *MirroredGraphStore) ListIncidentMemories(tenantID, environment string) []domain.IncidentMemory {
	return s.primary.ListIncidentMemories(tenantID, environment)
}

func (s *MirroredGraphStore) Ping() error {
	if checker, ok := s.primary.(interface{ Ping() error }); ok {
		if err := checker.Ping(); err != nil {
			return err
		}
	}
	for _, mirror := range s.mirrors {
		if checker, ok := mirror.(interface{ Ping() error }); ok {
			if err := checker.Ping(); err != nil {
				return err
			}
		}
	}
	return nil
}
