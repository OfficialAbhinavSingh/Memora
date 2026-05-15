package memory

import (
	"sync"

	"github.com/memora/pce/services/context-api/internal/domain"
)

type FeedbackStore struct {
	mu      sync.RWMutex
	records []domain.RemediationRecord
}

func NewFeedbackStore() *FeedbackStore {
	return &FeedbackStore{}
}

func (s *FeedbackStore) Record(remediation domain.RemediationRecord) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.records = append(s.records, remediation)
	return nil
}

func (s *FeedbackStore) List(tenantID, environment string) []domain.RemediationRecord {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var out []domain.RemediationRecord
	for _, record := range s.records {
		if record.TenantID == tenantID && record.Environment == environment {
			out = append(out, record)
		}
	}
	return out
}
