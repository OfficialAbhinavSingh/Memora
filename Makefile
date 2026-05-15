.PHONY: test fmt vet run web-lint web-build bench smoke docker-up docker-down

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

bench:
	python bench/worked_example_check.py

smoke:
	python bench/worked_example_check.py > bench-report.json && python bench/summarize_report.py bench-report.json

docker-up:
	docker compose up --build

docker-down:
	docker compose down
