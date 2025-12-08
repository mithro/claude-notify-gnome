# Makefile
.PHONY: test test-unit test-docker test-integration test-real test-notifications test-all docker-build clean

# Default: run unit tests locally
test: test-unit

# Run unit tests locally (fast, no Docker)
test-unit:
	uv run pytest tests/ -v --ignore=tests/e2e/

# Build Docker test images
docker-build:
	docker compose -f docker/docker-compose.test.yml build

# Run unit tests in Docker
test-docker: docker-build
	docker compose -f docker/docker-compose.test.yml run --rm unit-test

# Run mock integration tests in Docker
test-integration: docker-build
	docker compose -f docker/docker-compose.test.yml run --rm integration-test

# Run real Claude API tests (requires ANTHROPIC_API_KEY env var)
test-real: docker-build
	docker compose -f docker/docker-compose.test.yml run --rm real-claude-test

# Run GNOME notification tests
test-notifications: docker-build
	mkdir -p test-output
	docker compose -f docker/docker-compose.test.yml run --rm gnome-test

# Run all tests
test-all: test-unit test-integration test-notifications

# Clean up Docker resources
clean:
	docker compose -f docker/docker-compose.test.yml down --rmi local --volumes
