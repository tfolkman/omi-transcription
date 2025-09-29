# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OMI Transcription Service - A lightweight audio transcription service for OMI wearable devices that uses Groq's Whisper API for cost-effective speech-to-text conversion. The service receives audio from devices, transcribes it using Groq, and stores transcripts in Cloudflare R2 storage.

## Architecture

### Core Components

1. **FastAPI Application** (`app.py`): Main web server handling HTTP endpoints
   - `/audio` - Receives WAV files from OMI devices
   - `/streaming` - Handles real-time raw PCM audio streaming
   - `/transcripts/{uid}` - Retrieves user transcripts from R2 storage
   - `/stats` - Provides usage statistics and costs
   - `/health` - Service health check

2. **R2 Storage** (`r2_storage.py`): Cloudflare R2 integration for transcript storage
   - Uses environment-based bucket selection (omi-dev for development, omi for production)
   - Stores transcripts as JSON with zero egress fees
   - Implements boto3 S3-compatible API

3. **Transcription Service** (`transcription.py`): Groq Whisper API integration
   - Batch processes audio every 2 minutes for cost efficiency
   - Uses whisper-large-v3-turbo model ($0.04/hour of audio)
   - Handles both file uploads and streaming audio

4. **Audio Processing** (`audio_utils.py`): Audio format handling
   - Converts raw PCM to WAV format
   - Validates audio parameters
   - Adds proper WAV headers to streaming audio

5. **Configuration** (`config.py`): Environment-based configuration
   - Manages Groq API, R2 credentials, and batch settings
   - Supports development/production environments

## Development Commands

### Setup & Installation
```bash
# Install dependencies using UV
make install

# Install development dependencies
make dev

# Create .env from template
make setup-env
# Then add your GROQ_API_KEY and R2 credentials to .env
```

### Running the Service
```bash
# Run locally with UV
make run
# OR
uv run python app.py

# Run with specific environment
ENVIRONMENT=development uv run python app.py
```

### Code Quality
```bash
# Run linter
make lint
# OR
uv run ruff check .

# Format code
make format
# OR
uv run ruff format .

# Type checking
make type-check
# OR
uv run mypy app.py transcription.py config.py --ignore-missing-imports

# Security scan
make security
# OR
uv run bandit -r app.py transcription.py config.py
```

### Testing
```bash
# Run all tests
make test

# Run unit tests only
make test-unit
# OR
uv run pytest tests/test_unit.py -v

# Run E2E test with R2 storage
make test-e2e-r2
# OR
uv run python tests/test_e2e_r2.py

# Run streaming tests
uv run pytest tests/test_streaming.py -v

# Run specific test
uv run pytest tests/test_unit.py::test_validate_audio_params -v
```

### CI Checks (run locally before pushing)
```bash
# Run all CI checks
make ci-local
```

### Docker Operations
```bash
# Build Docker image
make docker-build

# Run with Docker Compose
make docker-run

# View Docker logs
make docker-logs

# Stop Docker containers
make docker-stop
```

### Debugging & Monitoring
```bash
# Check server status
make server-status

# Check audio queue
make queue-status

# Query recent transcripts (when using SQLite - legacy)
make db-query

# Test API endpoints
make test-api
```

## Environment Configuration

Required environment variables in `.env`:

```bash
# Groq API (required)
GROQ_API_KEY=your_groq_api_key

# R2 Storage (required for production)
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key

# Optional settings
ENVIRONMENT=development  # or production
BATCH_DURATION_SECONDS=120
MAX_BATCH_SIZE_MB=20
PORT=8000
HOST=0.0.0.0
```

## Key Implementation Details

### Storage Migration
The service has migrated from SQLite to Cloudflare R2:
- Development uses `omi-dev` bucket
- Production uses `omi` bucket
- Transcripts stored as JSON objects with path: `transcripts/{uid}/{timestamp}.json`

### Audio Processing Flow
1. OMI device sends audio via HTTP POST
2. Audio queued in filesystem (`data/audio_queue/`)
3. Batch processor runs every 2 minutes
4. Groq Whisper API transcribes audio
5. Results stored in R2 with metadata
6. Queue cleaned after successful processing

### Streaming Support
- Accepts raw PCM audio bytes
- Adds WAV headers dynamically
- Supports configurable sample rates
- Processes in real-time with minimal buffering

### Error Handling
- Comprehensive logging for debugging streaming issues
- Retry logic for API calls
- Graceful fallbacks for missing parameters
- Health checks include R2 connection status

## Testing Strategy

- **Unit Tests**: Core functions in `test_unit.py`
- **E2E Tests**: Full pipeline with R2 in `test_e2e_r2.py`
- **Streaming Tests**: Real-time audio handling in `test_streaming.py`
- Test audio generation utilities in `tests/utils/`

## Common Tasks

### Adding New Endpoints
1. Define endpoint in `app.py`
2. Add corresponding R2 operations if needed
3. Update tests in appropriate test file
4. Run `make ci-local` to verify

### Modifying Audio Processing
1. Update logic in `audio_utils.py` or `transcription.py`
2. Test with streaming endpoint: `curl -X POST "http://localhost:8000/streaming?uid=test"`
3. Verify with `make test-streaming`

### Updating Dependencies
1. Modify `pyproject.toml`
2. Run `uv lock` to update lock file
3. Run `uv sync` to install
4. Test with `make test`