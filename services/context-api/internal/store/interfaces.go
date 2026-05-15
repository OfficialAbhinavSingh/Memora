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
