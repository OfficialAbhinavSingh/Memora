package api

import (
	"fmt"
	"strings"
	"sync"
	"time"
)

type Stats struct {
	mu             sync.RWMutex
	requestsTotal  map[string]int64
	latencySeconds map[string]float64
}

func NewStats() *Stats {
	return &Stats{
		requestsTotal:  map[string]int64{},
		latencySeconds: map[string]float64{},
	}
}

func (s *Stats) Record(path string, status int, duration time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()

	key := fmt.Sprintf("%s|%d", normalizePath(path), status)
	s.requestsTotal[key]++
	s.latencySeconds[normalizePath(path)] += duration.Seconds()
}

func (s *Stats) Prometheus() string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var b strings.Builder
	b.WriteString("# TYPE pce_http_requests_total counter\n")
	for key, count := range s.requestsTotal {
		parts := strings.SplitN(key, "|", 2)
		b.WriteString(fmt.Sprintf("pce_http_requests_total{path=%q,status=%q} %d\n", parts[0], parts[1], count))
	}

	b.WriteString("# TYPE pce_http_request_latency_seconds_sum counter\n")
	for path, total := range s.latencySeconds {
		b.WriteString(fmt.Sprintf("pce_http_request_latency_seconds_sum{path=%q} %.6f\n", path, total))
	}

	return b.String()
}

func normalizePath(path string) string {
	if strings.HasPrefix(path, "/v1/incidents/") {
		return "/v1/incidents/{id}/memory"
	}
	return path
}
