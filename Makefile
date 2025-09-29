.PHONY: help install dev lint format test test-e2e test-unit run clean

help: ## Show this help message
	@echo "OMI Transcription Service - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with UV
	uv sync

dev: ## Install development dependencies
	uv sync --dev

run: ## Run the service locally
	uv run python app.py

lint: ## Run linter checks
	uv run ruff check .

format: ## Format code with ruff
	uv run ruff format .

type-check: ## Run type checking with mypy
	uv run mypy app.py transcription.py config.py --ignore-missing-imports

security: ## Run security scan with bandit
	uv run bandit -r app.py transcription.py config.py

test-unit: ## Run unit tests
	uv run pytest tests/test_unit.py -v

test-e2e-r2: ## Run E2E test with R2 storage
	@echo "Ensuring test audio exists..."
	@if [ ! -f tests/fixtures/test_speech.wav ]; then \
		echo "Converting audio..."; \
		uv run python tests/convert_audio.py; \
	fi
	@echo "Running E2E test with R2..."
	uv run python tests/test_e2e_r2.py

test-e2e: ## Run legacy E2E test (SQLite)
	@echo "Ensuring test audio exists..."
	@if [ ! -f tests/fixtures/test_speech.wav ]; then \
		echo "Converting audio..."; \
		uv run python tests/convert_audio.py; \
	fi
	@echo "Running E2E test..."
	uv run python tests/test_e2e.py

test: test-unit test-e2e-r2 ## Run all tests

ci-local: ## Run all CI checks locally
	@echo "Running CI checks locally..."
	$(MAKE) lint
	$(MAKE) format --check .
	$(MAKE) type-check
	$(MAKE) security
	$(MAKE) test-unit
	@echo "✅ All CI checks passed!"

test-api: ## Test API endpoints with curl
	./test_api.sh

clean: ## Clean up generated files and cache
	rm -rf __pycache__ .pytest_cache *.pyc
	rm -rf data/audio_queue/*.wav
	rm -f test_audio.wav test_*.wav

clean-db: ## Reset database (WARNING: deletes all data)
	rm -f data/transcripts.db
	@echo "Database reset. Will be recreated on next run."

docker-build: ## Build Docker image
	docker-compose build

docker-run: ## Run with Docker Compose
	docker-compose up -d

docker-stop: ## Stop Docker containers
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

setup-env: ## Create .env from template
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file. Please add your GROQ_API_KEY"; \
	else \
		echo ".env already exists"; \
	fi

server-status: ## Check if server is running
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "Server is not running"

queue-status: ## Check audio queue status
	@echo "Audio files in queue:"
	@ls -la data/audio_queue/ 2>/dev/null || echo "No queue directory"
	@echo ""
	@echo "Queue stats from API:"
	@curl -s http://localhost:8000/stats | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Pending files: {data[\"queue\"][\"pending_files\"]}')" 2>/dev/null || echo "Could not get stats"

db-query: ## Query database for recent transcripts
	@echo "Recent transcripts:"
	@sqlite3 -header -column data/transcripts.db "SELECT id, uid, substr(transcript_text,1,50) as transcript, cost_usd, datetime(created_at) as created FROM transcripts ORDER BY created_at DESC LIMIT 5;" 2>/dev/null || echo "No database found"