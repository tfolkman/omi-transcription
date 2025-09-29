# 🎤 OMI Real-Time Streaming Deployment Guide

This guide covers deploying the OMI Transcription Service with **real-time audio streaming** support on Oracle Cloud VM or any Linux server.

## 📋 Overview

The real-time streaming feature allows OMI devices to send continuous audio data in chunks, which the service processes and transcribes. Unlike the batch mode that expects complete WAV files, streaming mode handles raw PCM audio bytes.

### Key Differences from Batch Mode

| Feature | Batch Mode (`/audio`) | Streaming Mode (`/streaming`) |
|---------|----------------------|------------------------------|
| **Input Format** | Complete WAV files | Raw PCM audio bytes |
| **Headers Required** | Yes (WAV headers) | No (adds headers automatically) |
| **OMI Setting** | File upload | Real-time audio bytes |
| **Use Case** | Periodic uploads | Continuous streaming |
| **Endpoint** | `/audio` | `/streaming` |

## 🚀 Quick Start

### Prerequisites

- Oracle VM or Linux server with Docker
- Groq API key from [console.groq.com](https://console.groq.com)
- Cloudflare R2 account with credentials
- OMI device with firmware v1.0.4+ (supports streaming)

### Step 1: Deploy the Service

```bash
# SSH into your VM
ssh ubuntu@<your-vm-ip>

# Clone the repository
git clone https://github.com/yourusername/omi-transcription.git
cd omi-transcription

# Checkout the streaming branch
git checkout feature/omi-realtime-streaming

# Configure environment
cp .env.example .env
nano .env
```

Add your credentials to `.env`:
```env
# Environment
ENVIRONMENT=prod

# API Keys
GROQ_API_KEY=your_groq_api_key_here

# Cloudflare R2
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key

# Processing (adjust as needed)
BATCH_DURATION_SECONDS=60  # Process every minute for streaming
MAX_BATCH_SIZE_MB=20
```

### Step 2: Start the Service

```bash
# Build and start with Docker
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify health
curl http://localhost:8000/health
```

### Step 3: Configure OMI Device for Streaming

1. **Open OMI App** on your phone
2. Navigate to **Settings** → **Developer Mode**
3. Scroll to **Realtime audio bytes**
4. Configure:
   - **Webhook URL**: `http://<your-vm-ip>:8000/streaming`
   - **Every X seconds**: `10` (sends audio every 10 seconds)
5. **Enable** real-time streaming

## 📡 Streaming Endpoint Details

### Endpoint: `POST /streaming`

**Query Parameters:**
- `uid` (required): User identifier
- `sample_rate` (optional): Audio sample rate (default: 16000)

**Request Body:**
- Content-Type: `application/octet-stream`
- Body: Raw PCM audio bytes (no WAV header)

**Example Request from OMI:**
```
POST /streaming?sample_rate=16000&uid=user123
Content-Type: application/octet-stream
[raw PCM audio bytes]
```

**Response:**
```json
{
  "status": "queued",
  "uid": "user123",
  "filename": "streaming_user123_1234567890.wav",
  "size_mb": 0.15,
  "sample_rate": 16000,
  "raw_bytes_received": 160000,
  "message": "Streaming audio received and queued. Will be transcribed within 60 seconds."
}
```

## 🔧 Technical Details

### Audio Processing Flow

1. **OMI Device** captures audio continuously
2. Every X seconds, sends raw PCM bytes to webhook
3. **Service receives** raw audio at `/streaming` endpoint
4. **WAV headers added** automatically (16-bit, mono, 16kHz)
5. **Audio saved** to queue directory
6. **Batch processor** transcribes queued files
7. **Transcripts stored** in Cloudflare R2

### WAV Header Generation

The service automatically adds proper WAV headers to raw PCM data:

```python
# Audio parameters for OMI devices
- Sample Rate: 16000 Hz (16 kHz)
- Channels: 1 (Mono)
- Bit Depth: 16 bits
- Format: PCM (uncompressed)
```

## 🧪 Testing the Streaming Endpoint

### Test Script

Use the included test script to verify streaming functionality:

```bash
# Install test dependencies
pip install numpy httpx

# Run streaming test
python tests/test_streaming.py
```

### Manual Testing with curl

```bash
# Generate test audio (or use existing raw PCM file)
# This example uses sox to generate raw PCM
sox -n -r 16000 -b 16 -c 1 test.raw synth 5 sine 440

# Send to streaming endpoint
curl -X POST "http://<your-vm-ip>:8000/streaming?uid=test_user&sample_rate=16000" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @test.raw
```

### Verify Processing

```bash
# Check transcripts for user
curl "http://<your-vm-ip>:8000/transcripts/test_user"

# Monitor stats
curl "http://<your-vm-ip>:8000/stats"
```

## 📊 Monitoring & Costs

### Real-Time Streaming Costs

With Groq's Whisper API at $0.04/hour of audio:

| Streaming Interval | Audio/Day | Cost/Day | Cost/Month |
|-------------------|-----------|----------|------------|
| Every 10 seconds | 2.4 hours | $0.096 | $2.88 |
| Every 30 seconds | 0.8 hours | $0.032 | $0.96 |
| Every 60 seconds | 0.4 hours | $0.016 | $0.48 |

### Monitoring Commands

```bash
# View real-time logs
docker-compose logs -f omi-transcription

# Check queue status
curl http://<your-vm-ip>:8000/stats | jq '.'

# Monitor disk usage
df -h
du -sh ~/omi-transcription/data/audio_queue/

# Check transcription costs
curl http://<your-vm-ip>:8000/stats | jq '.current_month.total_cost_usd'
```

## 🐛 Troubleshooting

### Common Issues

#### 1. "No audio data received" Error

**Cause:** OMI device not sending data or network issues

**Solution:**
- Verify OMI app settings
- Check network connectivity
- Ensure firewall allows port 8000

#### 2. Audio Not Being Transcribed

**Cause:** Batch processor not running or API key issues

**Solution:**
```bash
# Check batch processor logs
docker-compose logs omi-transcription | grep "Batch"

# Verify Groq API key
docker-compose exec omi-transcription env | grep GROQ
```

#### 3. High Costs

**Cause:** Streaming interval too frequent

**Solution:**
- Increase "Every X seconds" in OMI app (30-60 seconds recommended)
- Monitor usage: `curl http://<your-vm-ip>:8000/stats`

### Debug Mode

Enable detailed logging:

```bash
# Edit docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG

# Restart
docker-compose restart
```

## 🔒 Security Considerations

### Recommended Security Measures

1. **Use HTTPS with Caddy or Nginx:**
```bash
# Add reverse proxy with SSL
caddy reverse-proxy --from yourdomain.com --to localhost:8000
```

2. **Add API Key Authentication:**
```env
# In .env
API_KEY=your_secure_api_key
```

3. **Implement Rate Limiting:**
- Limit requests per user
- Prevent abuse

4. **Monitor Usage:**
```bash
# Set up alerts for unusual activity
curl http://localhost:8000/stats | \
  jq '.current_month.files_processed'
```

## 📈 Performance Optimization

### For High-Volume Streaming

1. **Adjust Batch Size:**
```env
BATCH_DURATION_SECONDS=30  # Process more frequently
MAX_BATCH_SIZE_MB=10      # Smaller batches
```

2. **Increase Worker Resources:**
```yaml
# docker-compose.yml
services:
  omi-transcription:
    cpus: '2'
    mem_limit: 2g
```

3. **Use SSD Storage:**
```bash
# Move queue to SSD
ln -s /mnt/ssd/audio_queue ~/omi-transcription/data/audio_queue
```

## 🎯 Best Practices

1. **Optimal Streaming Interval:** 30-60 seconds balances cost and real-time needs
2. **Monitor Costs Daily:** Check `/stats` endpoint regularly
3. **Clean Old Files:** Set up cron job to remove processed audio
4. **Backup Transcripts:** R2 provides redundancy, but consider additional backups
5. **Test Updates:** Always test in dev environment first

## 📝 Configuration Reference

### Environment Variables

| Variable | Description | Default | Recommended |
|----------|-------------|---------|-------------|
| `ENVIRONMENT` | Deployment environment | `dev` | `prod` for Oracle VM |
| `GROQ_API_KEY` | Groq API key | Required | - |
| `R2_ACCOUNT_ID` | Cloudflare account | Required | - |
| `R2_ACCESS_KEY_ID` | R2 access key | Required | - |
| `R2_SECRET_ACCESS_KEY` | R2 secret | Required | - |
| `BATCH_DURATION_SECONDS` | Processing interval | 120 | 60 for streaming |
| `MAX_BATCH_SIZE_MB` | Max batch size | 20 | 20 |
| `PORT` | Service port | 8000 | 8000 |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/streaming` | POST | Real-time audio streaming |
| `/audio` | POST | Batch audio upload |
| `/transcripts/{uid}` | GET | Get user transcripts |
| `/stats` | GET | Usage statistics |

## 🆘 Support

If you encounter issues:

1. Check the [troubleshooting section](#-troubleshooting)
2. Review logs: `docker-compose logs --tail=100`
3. Test with the provided script: `python tests/test_streaming.py`
4. Open an issue on GitHub with:
   - Error messages
   - Log output
   - OMI device version
   - Configuration details

## ✅ Deployment Checklist

- [ ] Oracle VM accessible via SSH
- [ ] Docker and Docker Compose installed
- [ ] Repository cloned and streaming branch checked out
- [ ] `.env` file configured with all credentials
- [ ] Service started with `docker-compose up -d`
- [ ] Health check returns success
- [ ] Oracle firewall configured (port 8000 open)
- [ ] OMI app configured with streaming webhook
- [ ] Test audio successfully streamed and transcribed
- [ ] Monitoring set up for costs and usage

---

**Congratulations!** Your OMI Real-Time Streaming Service is now deployed! 🎉

Monitor your first streaming sessions at: `http://<your-vm-ip>:8000/stats`