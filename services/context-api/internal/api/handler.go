package api

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/memora/pce/services/context-api/internal/app"
	"github.com/memora/pce/services/context-api/internal/domain"
	"github.com/memora/pce/services/context-api/internal/service"
)

type Handler struct {
	engine *service.Engine
	cfg    app.Config
	stats  *Stats
}

func NewHandler(engine *service.Engine, cfg app.Config) *Handler {
	return &Handler{
		engine: engine,
		cfg:    cfg,
		stats:  NewStats(),
	}
}

func (h *Handler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /v1/health", h.health)
	mux.HandleFunc("GET /v1/readiness", h.readiness)
	mux.HandleFunc("GET /v1/metrics", h.metrics)
	mux.HandleFunc("POST /v1/ingest/events", h.ingestEvents)
	mux.HandleFunc("POST /v1/context/reconstruct", h.reconstructContext)
	mux.HandleFunc("GET /v1/incidents/", h.getIncidentMemory)
	mux.HandleFunc("POST /v1/feedback/remediation-outcome", h.recordFeedback)
	mux.HandleFunc("POST /v1/topology/alias", h.upsertAlias)
	return h.withMiddleware(mux)
}

func (h *Handler) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (h *Handler) readiness(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (h *Handler) metrics(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	_, _ = w.Write([]byte(h.stats.Prometheus()))
}

func (h *Handler) ingestEvents(w http.ResponseWriter, r *http.Request) {
	var req domain.IngestRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if err := h.engine.Ingest(req.Events); err != nil {
		writeEngineError(w, err)
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]int{"accepted": len(req.Events)})
}

func (h *Handler) reconstructContext(w http.ResponseWriter, r *http.Request) {
	var req domain.ReconstructRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	context, err := h.engine.Reconstruct(req)
	if err != nil {
		writeEngineError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, context)
}

func (h *Handler) getIncidentMemory(w http.ResponseWriter, r *http.Request) {
	prefix := "/v1/incidents/"
	if !strings.HasPrefix(r.URL.Path, prefix) || !strings.HasSuffix(r.URL.Path, "/memory") {
		http.NotFound(w, r)
		return
	}
	incidentID := strings.TrimSuffix(strings.TrimPrefix(r.URL.Path, prefix), "/memory")
	if incidentID == "" {
		http.NotFound(w, r)
		return
	}
	memory, ok := h.engine.GetIncidentMemory(incidentID)
	if !ok {
		http.NotFound(w, r)
		return
	}
	writeJSON(w, http.StatusOK, memory)
}

func (h *Handler) recordFeedback(w http.ResponseWriter, r *http.Request) {
	var req domain.FeedbackRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if err := h.engine.RecordFeedback(req); err != nil {
		writeEngineError(w, err)
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]string{"status": "recorded"})
}

func (h *Handler) upsertAlias(w http.ResponseWriter, r *http.Request) {
	var req domain.AliasRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if err := h.engine.UpsertAlias(req); err != nil {
		writeEngineError(w, err)
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]string{"status": "updated"})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, err error) {
	writeJSON(w, status, map[string]string{"error": err.Error()})
}

func writeEngineError(w http.ResponseWriter, err error) {
	if service.IsInvalidInput(err) {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	writeError(w, http.StatusInternalServerError, err)
}
