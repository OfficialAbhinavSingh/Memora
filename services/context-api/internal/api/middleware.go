package api

import (
	"crypto/subtle"
	"fmt"
	"log"
	"net/http"
	"runtime/debug"
	"strconv"
	"strings"
	"time"
)

const requestIDHeader = "X-Request-Id"

func (h *Handler) withMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		requestID := r.Header.Get(requestIDHeader)
		if requestID == "" {
			requestID = strconv.FormatInt(time.Now().UnixNano(), 36)
		}

		w.Header().Set(requestIDHeader, requestID)
		if h.cfg.MaxRequestBytes > 0 && r.Body != nil {
			r.Body = http.MaxBytesReader(w, r.Body, h.cfg.MaxRequestBytes)
		}

		recorder := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		defer func() {
			if recovered := recover(); recovered != nil {
				log.Printf("panic request_id=%s err=%v stack=%s", requestID, recovered, string(debug.Stack()))
				writeError(recorder, http.StatusInternalServerError, fmt.Errorf("internal server error"))
			}
			h.stats.Record(r.URL.Path, recorder.status, time.Since(start))
			log.Printf("request_id=%s method=%s path=%s status=%d duration=%s", requestID, r.Method, r.URL.Path, recorder.status, time.Since(start))
		}()

		if !h.authorized(r) {
			writeError(recorder, http.StatusUnauthorized, fmt.Errorf("unauthorized"))
			return
		}

		next.ServeHTTP(recorder, r)
	})
}

func (h *Handler) authorized(r *http.Request) bool {
	if h.cfg.APIKey == "" {
		return true
	}

	if r.URL.Path == "/v1/health" || r.URL.Path == "/v1/readiness" || r.URL.Path == "/v1/metrics" {
		return true
	}

	token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	if token == "" {
		token = r.Header.Get("X-PCE-API-Key")
	}

	return subtle.ConstantTimeCompare([]byte(token), []byte(h.cfg.APIKey)) == 1
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}
