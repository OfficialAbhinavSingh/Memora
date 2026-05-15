package app

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	Addr               string
	FastWindow         time.Duration
	DeepWindow         time.Duration
	SimilarityLookback time.Duration
	ClickHouseURL      string
	PostgresDSN        string
	APIKey             string
	ReadTimeout        time.Duration
	WriteTimeout       time.Duration
	ShutdownTimeout    time.Duration
	MaxRequestBytes    int64
}

func LoadConfig() Config {
	return Config{
		Addr:               envOrDefault("PCE_ADDR", ":8080"),
		FastWindow:         durationOrDefault("PCE_FAST_WINDOW", 30*time.Minute),
		DeepWindow:         durationOrDefault("PCE_DEEP_WINDOW", 4*time.Hour),
		SimilarityLookback: durationOrDefault("PCE_SIMILARITY_LOOKBACK", 30*24*time.Hour),
		ClickHouseURL:      envOrDefault("CLICKHOUSE_DSN", ""),
		PostgresDSN:        envOrDefault("POSTGRES_DSN", ""),
		APIKey:             os.Getenv("PCE_API_KEY"),
		ReadTimeout:        durationOrDefault("PCE_READ_TIMEOUT", 5*time.Second),
		WriteTimeout:       durationOrDefault("PCE_WRITE_TIMEOUT", 10*time.Second),
		ShutdownTimeout:    durationOrDefault("PCE_SHUTDOWN_TIMEOUT", 15*time.Second),
		MaxRequestBytes:    int64OrDefault("PCE_MAX_REQUEST_BYTES", 4<<20),
	}
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
