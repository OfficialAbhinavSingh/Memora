package clickhouse

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/memora/pce/services/context-api/internal/domain"
)

type TelemetryStore struct {
	baseURL string
	client  *http.Client
}

type row struct {
	EventID            string   `json:"event_id"`
	TS                 string   `json:"ts"`
	Kind               string   `json:"kind"`
	TenantID           string   `json:"tenant_id"`
	Environment        string   `json:"environment"`
	ServiceName        string   `json:"service_name"`
	CanonicalServiceID string   `json:"canonical_service_id"`
	IncidentID         string   `json:"incident_id"`
	TraceID            string   `json:"trace_id"`
	Entities           []string `json:"entities"`
	Attributes         string   `json:"attributes"`
	RawRef             string   `json:"raw_ref"`
	Provenance         string   `json:"provenance"`
}

func NewTelemetryStore(baseURL string) *TelemetryStore {
	return &TelemetryStore{
		baseURL: strings.TrimRight(baseURL, "/"),
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (s *TelemetryStore) Ping() error {
	respBody, err := s.query(context.Background(), "SELECT 1 FORMAT JSONEachRow")
	if err != nil {
		return err
	}
	return respBody.Close()
}

func (s *TelemetryStore) Append(events []domain.Event) error {
	var body bytes.Buffer
	encoder := json.NewEncoder(&body)
	for _, event := range events {
		record, err := marshalRow(event)
		if err != nil {
			return err
		}
		if err := encoder.Encode(record); err != nil {
			return err
		}
	}

	query := "INSERT INTO telemetry_events FORMAT JSONEachRow"
	return s.exec(context.Background(), query, &body)
}

func (s *TelemetryStore) List(filter domain.RelatedEventFilter) ([]domain.Event, error) {
	var where []string
	if filter.TenantID != "" {
		where = append(where, "tenant_id = '"+escape(filter.TenantID)+"'")
	}
	if filter.Environment != "" {
		where = append(where, "environment = '"+escape(filter.Environment)+"'")
	}
	if !filter.From.IsZero() {
		where = append(where, "ts >= parseDateTime64BestEffort('"+filter.From.UTC().Format(time.RFC3339Nano)+"')")
	}
	if !filter.To.IsZero() {
		where = append(where, "ts <= parseDateTime64BestEffort('"+filter.To.UTC().Format(time.RFC3339Nano)+"')")
	}
	if filter.TraceID != "" {
		where = append(where, "trace_id = '"+escape(filter.TraceID)+"'")
	}
	if filter.IncidentID != "" {
		where = append(where, "(incident_id = '' OR incident_id = '"+escape(filter.IncidentID)+"')")
	}
	if len(filter.ServiceNames) > 0 {
		var servicePredicates []string
		for _, service := range filter.ServiceNames {
			if strings.TrimSpace(service) == "" {
				continue
			}
			quoted := "'" + escape(service) + "'"
			servicePredicates = append(servicePredicates,
				"service_name = "+quoted,
				"canonical_service_id = "+quoted,
				"has(entities, "+quoted+")",
				"positionCaseInsensitive(attributes, "+quoted+") > 0",
			)
		}
		if len(servicePredicates) > 0 {
			where = append(where, "("+strings.Join(servicePredicates, " OR ")+")")
		}
	}

	query := "SELECT event_id, ts, kind, tenant_id, environment, service_name, canonical_service_id, incident_id, trace_id, entities, attributes, raw_ref, provenance FROM telemetry_events"
	if len(where) > 0 {
		query += " WHERE " + strings.Join(where, " AND ")
	}
	query += " ORDER BY ts ASC, event_id ASC FORMAT JSONEachRow"

	respBody, err := s.query(context.Background(), query)
	if err != nil {
		return nil, err
	}
	defer respBody.Close()

	scanner := bufio.NewScanner(respBody)
	scanner.Buffer(make([]byte, 0, 1024), 1024*1024)

	var out []domain.Event
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			continue
		}
		var stored row
		if err := json.Unmarshal(line, &stored); err != nil {
			return nil, err
		}
		event, err := unmarshalRow(stored)
		if err != nil {
			return nil, err
		}
		out = append(out, event)
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	return out, nil
}

func (s *TelemetryStore) exec(ctx context.Context, query string, body io.Reader) error {
	endpoint, err := url.Parse(s.baseURL)
	if err != nil {
		return err
	}
	params := endpoint.Query()
	params.Set("query", query)
	endpoint.RawQuery = params.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint.String(), body)
	if err != nil {
		return err
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		payload, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("clickhouse write failed: %s", strings.TrimSpace(string(payload)))
	}

	return nil
}

func (s *TelemetryStore) query(ctx context.Context, query string) (io.ReadCloser, error) {
	endpoint, err := url.Parse(s.baseURL)
	if err != nil {
		return nil, err
	}
	params := endpoint.Query()
	params.Set("query", query)
	endpoint.RawQuery = params.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint.String(), nil)
	if err != nil {
		return nil, err
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 300 {
		defer resp.Body.Close()
		payload, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("clickhouse query failed: %s", strings.TrimSpace(string(payload)))
	}

	return resp.Body, nil
}

func marshalRow(event domain.Event) (row, error) {
	attributes, err := json.Marshal(event.Attributes)
	if err != nil {
		return row{}, err
	}
	provenance, err := json.Marshal(event.Provenance)
	if err != nil {
		return row{}, err
	}

	return row{
		EventID:            event.EventID,
		TS:                 event.TS.UTC().Format(time.RFC3339Nano),
		Kind:               event.Kind,
		TenantID:           event.TenantID,
		Environment:        event.Environment,
		ServiceName:        event.ServiceName,
		CanonicalServiceID: event.CanonicalServiceID,
		IncidentID:         event.IncidentID,
		TraceID:            event.TraceID,
		Entities:           event.Entities,
		Attributes:         string(attributes),
		RawRef:             event.RawRef,
		Provenance:         string(provenance),
	}, nil
}

func unmarshalRow(stored row) (domain.Event, error) {
	ts, err := time.Parse(time.RFC3339Nano, stored.TS)
	if err != nil {
		return domain.Event{}, err
	}

	attributes := map[string]any{}
	if strings.TrimSpace(stored.Attributes) != "" {
		if err := json.Unmarshal([]byte(stored.Attributes), &attributes); err != nil {
			return domain.Event{}, err
		}
	}

	provenance := map[string]any{}
	if strings.TrimSpace(stored.Provenance) != "" {
		if err := json.Unmarshal([]byte(stored.Provenance), &provenance); err != nil {
			return domain.Event{}, err
		}
	}

	return domain.Event{
		EventID:            stored.EventID,
		TS:                 ts,
		Kind:               stored.Kind,
		TenantID:           stored.TenantID,
		Environment:        stored.Environment,
		ServiceName:        stored.ServiceName,
		CanonicalServiceID: stored.CanonicalServiceID,
		IncidentID:         stored.IncidentID,
		TraceID:            stored.TraceID,
		Entities:           stored.Entities,
		Attributes:         attributes,
		RawRef:             stored.RawRef,
		Provenance:         provenance,
	}, nil
}

func escape(value string) string {
	return strings.ReplaceAll(value, "'", "\\'")
}
