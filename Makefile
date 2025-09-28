.PHONY: help install run test test-e2e test-local clean docker-build docker-run docker-stop

help: ## Show this help message
	@echo "OMI Transcription Service - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with UV
	uv sync

run: ## Run the service locally
	uv run python app.py

test: test-local test-e2e ## Run all tests

test-local: ## Run local unit tests (mocked)
	uv run python test_local.py

test-e2e: ## Run end-to-end test (requires server running)
	@echo "Ensuring test audio exists..."
	@if [ ! -f tests/fixtures/test_speech.wav ]; then \
		echo "Converting audio..."; \
		uv run python tests/convert_audio.py; \
	fi
	@echo "Running E2E test..."
	uv run python tests/test_e2e.py

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