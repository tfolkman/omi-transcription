# GitHub Actions Secrets Setup

To enable CI/CD for this repository, you need to configure the following GitHub Secrets:

## Required Secrets

### 1. Cloudflare R2 Credentials
- `R2_ACCOUNT_ID`: Your Cloudflare account ID
- `R2_ACCESS_KEY_ID`: R2 API access key
- `R2_SECRET_ACCESS_KEY`: R2 API secret key

### 2. Groq API
- `GROQ_API_KEY`: Your Groq API key for Whisper transcription

## How to Add Secrets

1. Go to your GitHub repository
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its name and value

## Getting the Credentials

### Cloudflare R2:
1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Go to R2 → Manage R2 API Tokens
3. Create a new API token with Object Read & Write permissions
4. Copy the credentials

### Groq API:
1. Sign up at [console.groq.com](https://console.groq.com)
2. Go to API Keys section
3. Create a new API key
4. Copy the key

## CI/CD Pipeline Features

The GitHub Actions workflow will:

1. **Linting & Formatting** (on every PR)
   - Runs `ruff` for code style checking
   - Ensures consistent formatting

2. **Type Checking** (on every PR)
   - Runs `mypy` for type validation
   - Helps catch type-related bugs early

3. **Security Scanning** (on every PR)
   - Runs `bandit` to detect security issues
   - Identifies potential vulnerabilities

4. **E2E Testing** (on every PR)
   - Uploads test audio to R2
   - Verifies transcription works
   - Checks R2 storage integration
   - Validates API endpoints

5. **Auto-merge** (optional)
   - Can auto-merge PRs that pass all tests
   - Requires adding `automerge` label to PR

## Test Environment

The CI uses:
- `omi-dev` bucket for development/testing
- `omi` bucket for production (when deployed)

## Local Testing

Before pushing, you can run the same checks locally:

```bash
# Linting
uv run ruff check .
uv run ruff format --check .

# Type checking
uv run mypy app.py transcription.py config.py

# Security scan
uv run bandit -r app.py transcription.py config.py

# E2E test
uv run python tests/test_e2e_r2.py
```

## Troubleshooting

If CI fails:
1. Check the workflow logs in the Actions tab
2. Ensure all secrets are properly configured
3. Verify R2 buckets exist (`omi-dev` for testing)
4. Check that Groq API key has sufficient quota