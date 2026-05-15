.PHONY: test fmt vet run web-lint web-build web-docker bench smoke docker-up docker-down

test:
	cd services/context-api && go test ./...

fmt:
	cd services/context-api && gofmt -l -w .

vet:
	cd services/context-api && go vet ./...

run:
	cd services/context-api && go run ./cmd/context-api

web-lint:
	cd web && npm run lint

web-build:
	cd web && npm run build

web-docker:
	docker build web -t pce/web-ui:local

bench:
	sh bench/run.sh

smoke:
	python bench/worked_example_check.py
	python bench/regression_check.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down
