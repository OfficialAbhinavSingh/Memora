package domain

import "time"

type Mode string

const (
	ModeFast Mode = "fast"
	ModeDeep Mode = "deep"
)

type Event struct {
	EventID            string         `json:"event_id"`
	TS                 time.Time      `json:"ts"`
	Kind               string         `json:"kind"`
	TenantID           string         `json:"tenant_id"`
	Environment        string         `json:"environment"`
	ServiceName        string         `json:"service_name,omitempty"`
	CanonicalServiceID string         `json:"canonical_service_id,omitempty"`
	IncidentID         string         `json:"incident_id,omitempty"`
	TraceID            string         `json:"trace_id,omitempty"`
	Entities           []string       `json:"entities,omitempty"`
	Attributes         map[string]any `json:"attributes,omitempty"`
	RawRef             string         `json:"raw_ref,omitempty"`
	Provenance         map[string]any `json:"provenance,omitempty"`
}

type IncidentSignal struct {
	IncidentID         string            `json:"incident_id"`
	TS                 time.Time         `json:"ts"`
	TenantID           string            `json:"tenant_id"`
	Environment        string            `json:"environment"`
	ServiceName        string            `json:"service_name,omitempty"`
	CanonicalServiceID string            `json:"canonical_service_id,omitempty"`
	Trigger            string            `json:"trigger"`
	Attributes         map[string]string `json:"attributes,omitempty"`
}

type CausalEdge struct {
	CauseID    string   `json:"cause_id"`
	EffectID   string   `json:"effect_id"`
	Evidence   []string `json:"evidence"`
	Confidence float64  `json:"confidence"`
}

type IncidentMatch struct {
	PastIncidentID string  `json:"past_incident_id"`
	Similarity     float64 `json:"similarity"`
	Rationale      string  `json:"rationale"`
}

type Remediation struct {
	Action            string  `json:"action"`
	Target            string  `json:"target"`
	HistoricalOutcome string  `json:"historical_outcome"`
	Confidence        float64 `json:"confidence"`
}

type Context struct {
	RelatedEvents         []Event         `json:"related_events"`
	CausalChain           []CausalEdge    `json:"causal_chain"`
	SimilarPastIncidents  []IncidentMatch `json:"similar_past_incidents"`
	SuggestedRemediations []Remediation   `json:"suggested_remediations"`
	Confidence            float64         `json:"confidence"`
	Explain               string          `json:"explain"`
}

type ReconstructRequest struct {
	Signal IncidentSignal `json:"signal"`
	Mode   Mode           `json:"mode"`
}

type IngestRequest struct {
	Events []Event `json:"events"`
}

type FeedbackRequest struct {
	IncidentID   string    `json:"incident_id"`
	TenantID     string    `json:"tenant_id"`
	Environment  string    `json:"environment"`
	Action       string    `json:"action"`
	Target       string    `json:"target"`
	Outcome      string    `json:"outcome"`
	Version      string    `json:"version,omitempty"`
	ObservedAt   time.Time `json:"observed_at"`
	ServiceName  string    `json:"service_name,omitempty"`
	AliasService string    `json:"canonical_service_id,omitempty"`
}

type AliasRequest struct {
	TenantID    string    `json:"tenant_id"`
	Environment string    `json:"environment"`
	From        string    `json:"from"`
	To          string    `json:"to"`
	ObservedAt  time.Time `json:"observed_at"`
	Confidence  float64   `json:"confidence"`
}

type IncidentMemory struct {
	Signal  IncidentSignal `json:"signal"`
	Context Context        `json:"context"`
}

type RelatedEventFilter struct {
	TenantID     string
	Environment  string
	ServiceNames []string
	TraceID      string
	IncidentID   string
	From         time.Time
	To           time.Time
}

type AliasRecord struct {
	TenantID           string
	Environment        string
	From               string
	To                 string
	CanonicalServiceID string
	Confidence         float64
	ObservedAt         time.Time
}

type RemediationRecord struct {
	IncidentID         string
	TenantID           string
	Environment        string
	Action             string
	Target             string
	Outcome            string
	Version            string
	ObservedAt         time.Time
	ServiceName        string
	CanonicalServiceID string
}
