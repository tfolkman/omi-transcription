# 🚀 Oracle VM Deployment Guide

Complete step-by-step guide for deploying the OMI Transcription Service on Oracle Cloud Free Tier VM.

## Prerequisites

- Oracle Cloud account with free tier VM (ARM or AMD)
- SSH access to your VM
- Groq API key from [console.groq.com](https://console.groq.com)

## Step 1: Access Your Oracle VM

```bash
# Replace with your actual VM IP
ssh ubuntu@<your-oracle-vm-ip>

# Or if using a different user/key
ssh -i ~/.ssh/your_key.pem ubuntu@<your-oracle-vm-ip>
```

## Step 2: System Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl wget git nano
```

## Step 3: Install Docker

```bash
# Download Docker installation script
curl -fsSL https://get.docker.com -o get-docker.sh

# Run installation
sudo sh get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER

# Apply group changes (logout and login again, or use this)
newgrp docker

# Verify installation
docker --version
docker run hello-world
```

## Step 4: Install Docker Compose

```bash
# Install Docker Compose
sudo apt install -y docker-compose

# Verify installation
docker-compose --version
```

## Step 5: Setup Project

### Option A: Clone from Git Repository

```bash
# Clone your repository
git clone https://github.com/yourusername/omi-transcription.git
cd omi-transcription
```

### Option B: Manual File Creation

```bash
# Create project directory
mkdir -p ~/omi-transcription
cd ~/omi-transcription

# Now copy all files from your local machine to the VM
# You can use scp from your local machine:
# scp -r /path/to/omi-transcription/* ubuntu@<vm-ip>:~/omi-transcription/
```

## Step 6: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your Groq API key
nano .env

# Add your key (press Ctrl+X, then Y to save):
# GROQ_API_KEY=your_actual_groq_api_key_here
# BATCH_DURATION_SECONDS=120
# MAX_BATCH_SIZE_MB=20
# PORT=8000
# HOST=0.0.0.0
```

## Step 7: Configure Oracle Cloud Firewall

### A. Security List Configuration

1. Log into [Oracle Cloud Console](https://cloud.oracle.com)
2. Navigate to: **Networking** → **Virtual Cloud Networks**
3. Click on your VCN (Virtual Cloud Network)
4. Click on **Security Lists** in the left menu
5. Click on the Default Security List
6. Click **Add Ingress Rules**
7. Add the following rule:

   ```
   Source Type: CIDR
   Source CIDR: 0.0.0.0/0
   IP Protocol: TCP
   Source Port Range: (leave blank for all)
   Destination Port Range: 8000
   Description: OMI Transcription Service
   ```

8. Click **Add Ingress Rules** to save

### B. Ubuntu Firewall (if enabled)

```bash
# Check if firewall is active
sudo ufw status

# If active, allow port 8000
sudo ufw allow 8000/tcp
sudo ufw reload
```

## Step 8: Start the Service

```bash
# Build and start the service
docker-compose up -d

# Check if containers are running
docker-compose ps

# View logs
docker-compose logs -f

# Press Ctrl+C to exit log view
```

## Step 9: Verify Deployment

```bash
# Test locally on VM
curl http://localhost:8000/health

# Test from your local machine
curl http://<your-oracle-vm-ip>:8000/health

# Expected response:
# {"status":"healthy","timestamp":"2024-01-01T00:00:00.000000"}
```

## Step 10: Configure OMI Device

1. Open OMI app on your phone
2. Go to **Settings** → **Developer Options**
3. Configure:
   - **Webhook URL**: `http://<your-oracle-vm-ip>:8000/audio`
   - **Audio Duration**: 120-300 seconds
   - **Audio Format**: WAV

## Managing the Service

### View Status

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f omi-transcription

# View last 100 lines
docker-compose logs --tail=100
```

### Stop Service

```bash
docker-compose stop
```

### Start Service

```bash
docker-compose start
```

### Restart Service

```bash
docker-compose restart
```

### Update Service

```bash
# Pull latest changes (if using git)
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### Remove Service

```bash
# Stop and remove containers
docker-compose down

# Remove with volumes (deletes database)
docker-compose down -v
```

## Monitoring

### Check API Stats

```bash
# From VM
curl http://localhost:8000/stats | python3 -m json.tool

# From your computer
curl http://<your-oracle-vm-ip>:8000/stats | python3 -m json.tool
```

### Check User Transcripts

```bash
# Replace 'user123' with actual user ID
curl http://<your-oracle-vm-ip>:8000/transcripts/user123
```

### Monitor Disk Usage

```bash
# Check overall disk usage
df -h

# Check Docker usage
docker system df

# Check data directory size
du -sh ~/omi-transcription/data/
```

### View Database

```bash
# Install SQLite (if needed)
sudo apt install -y sqlite3

# Open database
sqlite3 ~/omi-transcription/data/transcripts.db

# Example queries
.tables
SELECT * FROM transcripts LIMIT 5;
SELECT COUNT(*) FROM transcripts;
SELECT SUM(cost_usd) FROM transcripts;
.quit
```

## Troubleshooting

### Service Not Accessible

1. **Check if container is running:**
   ```bash
   docker-compose ps
   ```

2. **Check firewall rules:**
   - Oracle Security List (via web console)
   - Ubuntu firewall: `sudo ufw status`

3. **Check logs for errors:**
   ```bash
   docker-compose logs --tail=50
   ```

### GROQ API Errors

1. **Verify API key:**
   ```bash
   cat .env | grep GROQ_API_KEY
   ```

2. **Test API key:**
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        https://api.groq.com/openai/v1/models
   ```

### Disk Space Issues

```bash
# Clean up Docker
docker system prune -a

# Remove old audio files (if any stuck)
rm ~/omi-transcription/data/audio_queue/*.wav

# Check and rotate database if too large
ls -lh ~/omi-transcription/data/transcripts.db
```

### Memory Issues

```bash
# Check memory usage
free -h

# Check container resources
docker stats

# Limit container memory (edit docker-compose.yml)
# Add under the service:
#   deploy:
#     resources:
#       limits:
#         memory: 512M
```

## Backup

### Database Backup

```bash
# Create backup directory
mkdir -p ~/backups

# Backup database
cp ~/omi-transcription/data/transcripts.db ~/backups/transcripts_$(date +%Y%m%d).db

# Compress backup
gzip ~/backups/transcripts_$(date +%Y%m%d).db
```

### Automated Backup (Cron)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cp ~/omi-transcription/data/transcripts.db ~/backups/transcripts_$(date +\%Y\%m\%d).db
```

## Security Hardening

### 1. Use HTTPS (with Caddy)

```bash
# Create Caddyfile
cat > ~/omi-transcription/Caddyfile <<EOF
your-domain.com {
    reverse_proxy localhost:8000
}
EOF

# Add Caddy to docker-compose.yml
# (See advanced setup documentation)
```

### 2. API Key Authentication

Add to `.env`:
```bash
API_KEY=your_secret_api_key
```

### 3. Rate Limiting

Configure in nginx or application level.

## Cost Monitoring

```bash
# Create monitoring script
cat > ~/check_costs.sh <<'EOF'
#!/bin/bash
echo "OMI Transcription Service - Cost Report"
echo "======================================="
curl -s http://localhost:8000/stats | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Files Processed: {data['current_month']['files_processed']}\")
print(f\"Current Month Cost: ${data['current_month']['total_cost_usd']:.4f}\")
print(f\"Estimated Monthly: ${data['current_month']['estimated_monthly_cost']:.2f}\")
print(f\"Pending Files: {data['queue']['pending_files']}\")
"
EOF

chmod +x ~/check_costs.sh
./check_costs.sh
```

## Support

If you encounter issues:

1. Check the logs first: `docker-compose logs --tail=100`
2. Verify all services are running: `docker-compose ps`
3. Test the health endpoint: `curl http://localhost:8000/health`
4. Check the troubleshooting section above
5. Review Oracle VM network settings

## Success Checklist

- [ ] VM is accessible via SSH
- [ ] Docker and Docker Compose installed
- [ ] Project files deployed
- [ ] `.env` configured with Groq API key
- [ ] Oracle firewall configured (port 8000)
- [ ] Service started with `docker-compose up -d`
- [ ] Health check returns success
- [ ] OMI device configured with webhook URL
- [ ] Test audio successfully uploaded
- [ ] Transcripts retrievable via API

---

**Congratulations!** Your OMI Transcription Service is now running on Oracle Cloud! 🎉