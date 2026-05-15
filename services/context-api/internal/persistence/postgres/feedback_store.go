package postgres

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/memora/pce/services/context-api/internal/domain"
)

type FeedbackStore struct {
	pool *pgxpool.Pool
}

func NewFeedbackStore(pool *pgxpool.Pool) *FeedbackStore {
	return &FeedbackStore{pool: pool}
}

func (s *FeedbackStore) Ping() error {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	return s.pool.Ping(ctx)
}

func (s *FeedbackStore) Record(remediation domain.RemediationRecord) error {
	_, err := s.pool.Exec(context.Background(), `
		INSERT INTO remediation_feedback
		    (incident_id, tenant_id, environment, action, target, outcome, version, service_name, canonical_service_id, observed_at)
		VALUES
		    ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
	`,
		remediation.IncidentID,
		remediation.TenantID,
		remediation.Environment,
		remediation.Action,
		remediation.Target,
		remediation.Outcome,
		remediation.Version,
		remediation.ServiceName,
		remediation.CanonicalServiceID,
		remediation.ObservedAt.UTC(),
	)
	return err
}

func (s *FeedbackStore) List(tenantID, environment string) []domain.RemediationRecord {
	rows, err := s.pool.Query(context.Background(), `
		SELECT incident_id, tenant_id, environment, action, target, outcome, version, service_name, canonical_service_id, observed_at
		FROM remediation_feedback
		WHERE tenant_id = $1 AND environment = $2
		ORDER BY observed_at ASC
	`, tenantID, environment)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var out []domain.RemediationRecord
	for rows.Next() {
		var record domain.RemediationRecord
		if err := rows.Scan(
			&record.IncidentID,
			&record.TenantID,
			&record.Environment,
			&record.Action,
			&record.Target,
			&record.Outcome,
			&record.Version,
			&record.ServiceName,
			&record.CanonicalServiceID,
			&record.ObservedAt,
		); err != nil {
			return out
		}
		out = append(out, record)
	}

	return out
}
