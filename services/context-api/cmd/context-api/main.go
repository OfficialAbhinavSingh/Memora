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
	"github.com/memora/pce/services/context-api/internal/service"
)

func main() {
	cfg := app.LoadConfig()

	telemetryStore := memory.NewTelemetryStore()
	graphStore := memory.NewGraphStore()
	feedbackStore := memory.NewFeedbackStore()
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
