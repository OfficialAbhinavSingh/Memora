.PHONY: test run docker-up docker-down

test:
	cd services/context-api && go test ./...

run:
	cd services/context-api && go run ./cmd/context-api

docker-up:
	docker compose up --build

docker-down:
	docker compose down
