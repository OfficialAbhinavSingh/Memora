package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/memora/pce/services/context-api/internal/api"
	"github.com/memora/pce/services/context-api/internal/app"
	"github.com/memora/pce/services/context-api/internal/memory"
	chstore "github.com/memora/pce/services/context-api/internal/persistence/clickhouse"
	neo4jstore "github.com/memora/pce/services/context-api/internal/persistence/neo4j"
	pgstore "github.com/memora/pce/services/context-api/internal/persistence/postgres"
	"github.com/memora/pce/services/context-api/internal/service"
	"github.com/memora/pce/services/context-api/internal/store"
)

func main() {
	cfg := app.LoadConfig()

	telemetryStore, graphStore, feedbackStore, closers := buildStores(cfg)
	defer closeAll(closers)

	engine := service.NewEngine(telemetryStore, graphStore, feedbackStore, cfg)

	handler := api.NewHandler(engine, cfg)

	server := &http.Server{
		Addr:         cfg.Addr,
		Handler:      handler.Routes(),
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}

	errs := make(chan error, 1)
	go func() {
		log.Printf("persistent context engine listening on %s", cfg.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errs <- err
		}
	}()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)

	select {
	case err := <-errs:
		log.Fatal(err)
	case sig := <-signals:
		log.Printf("received %s, shutting down", sig)
		ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(ctx); err != nil {
			log.Fatal(err)
		}
	}
}

type closer interface {
	Close()
}

func buildStores(cfg app.Config) (store.TelemetryStore, store.GraphStore, store.FeedbackStore, []closer) {
	telemetryStore := store.TelemetryStore(memory.NewTelemetryStore())
	graphStore := store.GraphStore(memory.NewGraphStore())
	feedbackStore := store.FeedbackStore(memory.NewFeedbackStore())
	var closers []closer

	if cfg.ClickHouseURL != "" {
		telemetryStore = chstore.NewTelemetryStore(cfg.ClickHouseURL)
		log.Printf("using clickhouse telemetry store at %s", cfg.ClickHouseURL)
	}

	if cfg.PostgresDSN != "" {
		pool, err := pgstore.NewPool(cfg.PostgresDSN)
		if err != nil {
			log.Fatalf("connect postgres: %v", err)
		}
		closers = append(closers, pool)
		graphStore = pgstore.NewGraphStore(pool)
		feedbackStore = pgstore.NewFeedbackStore(pool)
		log.Printf("using postgres graph and feedback stores")
	}

	if cfg.Neo4jURI != "" {
		neo4jGraph := neo4jstore.NewGraphStore(cfg.Neo4jURI, cfg.Neo4jUser, cfg.Neo4jPassword)
		graphStore = store.NewMirroredGraphStore(graphStore, neo4jGraph)
		log.Printf("mirroring graph relationships to neo4j at %s", cfg.Neo4jURI)
	}

	return telemetryStore, graphStore, feedbackStore, closers
}

func closeAll(closers []closer) {
	for _, closer := range closers {
		closer.Close()
	}
}
