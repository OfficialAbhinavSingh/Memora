package app

import (
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	Addr               string
	FastWindow         time.Duration
	DeepWindow         time.Duration
	SimilarityLookback time.Duration
	ClickHouseURL      string
	PostgresDSN        string
	Neo4jURI           string
	Neo4jUser          string
	Neo4jPassword      string
	APIKey             string
	// AllowedOrigins is the comma-separated list of origins permitted for
	// cross-origin requests. When empty the CORS middleware is disabled, which
	// is the correct setting when Nginx serves the UI and the API on the same
	// origin. Set PCE_ALLOWED_ORIGINS when the frontend is hosted on a
	// separate subdomain or CDN.
	AllowedOrigins  []string
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
	MaxRequestBytes int64
}

func LoadConfig() Config {
	return Config{
		Addr:               envOrDefault("PCE_ADDR", ":8080"),
		FastWindow:         durationOrDefault("PCE_FAST_WINDOW", 30*time.Minute),
		DeepWindow:         durationOrDefault("PCE_DEEP_WINDOW", 4*time.Hour),
		SimilarityLookback: durationOrDefault("PCE_SIMILARITY_LOOKBACK", 30*24*time.Hour),
		ClickHouseURL:      envOrDefault("CLICKHOUSE_DSN", ""),
		PostgresDSN:        envOrDefault("POSTGRES_DSN", ""),
		Neo4jURI:           envOrDefault("NEO4J_URI", ""),
		Neo4jUser:          envOrDefault("NEO4J_USER", ""),
		Neo4jPassword:      envOrDefault("NEO4J_PASSWORD", ""),
		APIKey:             os.Getenv("PCE_API_KEY"),
		AllowedOrigins:     parseOrigins(os.Getenv("PCE_ALLOWED_ORIGINS")),
		ReadTimeout:        durationOrDefault("PCE_READ_TIMEOUT", 5*time.Second),
		WriteTimeout:       durationOrDefault("PCE_WRITE_TIMEOUT", 10*time.Second),
		ShutdownTimeout:    durationOrDefault("PCE_SHUTDOWN_TIMEOUT", 15*time.Second),
		MaxRequestBytes:    int64OrDefault("PCE_MAX_REQUEST_BYTES", 4<<20),
	}
}

// parseOrigins splits a comma-separated origin list and trims whitespace.
// Returns nil when the value is empty, which disables CORS.
func parseOrigins(raw string) []string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}

func envOrDefault(key, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}

func durationOrDefault(key string, fallback time.Duration) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}

	parsed, err := time.ParseDuration(value)
	if err != nil {
		return fallback
	}

	return parsed
}

func int64OrDefault(key string, fallback int64) int64 {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}

	parsed, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return fallback
	}

	return parsed
}
