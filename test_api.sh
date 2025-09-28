#!/bin/bash

# Test script for OMI Transcription Service API
# Usage: ./test_api.sh

API_URL="${API_URL:-http://localhost:8000}"
TEST_USER="test_user_$(date +%s)"

echo "🔧 Testing OMI Transcription Service at $API_URL"
echo "================================================"

# Test 1: Health Check
echo -e "\n📍 Test 1: Health Check"
curl -s "$API_URL/health" | python3 -m json.tool
echo ""

# Test 2: Generate test audio file if it doesn't exist
echo -e "\n📍 Test 2: Creating test audio file"
if [ ! -f "test_audio.wav" ]; then
    # Create a simple test WAV file using sox or ffmpeg if available
    if command -v sox &> /dev/null; then
        sox -n -r 16000 -c 1 test_audio.wav synth 3 sine 440
        echo "✅ Created test audio with sox"
    elif command -v ffmpeg &> /dev/null; then
        ffmpeg -f lavfi -i "sine=frequency=440:duration=3" -ar 16000 -ac 1 test_audio.wav -y 2>/dev/null
        echo "✅ Created test audio with ffmpeg"
    else
        echo "⚠️  sox or ffmpeg not found. Please create test_audio.wav manually"
        echo "   You can use any WAV file for testing"
    fi
else
    echo "✅ Using existing test_audio.wav"
fi

# Test 3: Upload Audio
if [ -f "test_audio.wav" ]; then
    echo -e "\n📍 Test 3: Uploading audio file"
    UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/audio" \
        -F "file=@test_audio.wav" \
        -F "uid=$TEST_USER" \
        -F "sample_rate=16000")

    echo "$UPLOAD_RESPONSE" | python3 -m json.tool
    echo ""
else
    echo "⚠️  Skipping audio upload test - no test file available"
fi

# Test 4: Get Stats
echo -e "\n📍 Test 4: Getting usage statistics"
curl -s "$API_URL/stats" | python3 -m json.tool
echo ""

# Test 5: Wait for processing (if audio was uploaded)
if [ -f "test_audio.wav" ]; then
    echo -e "\n📍 Test 5: Waiting for batch processing..."
    echo "   (Batch processing runs every 120 seconds by default)"
    echo "   You can check transcripts after the batch runs:"
    echo ""
    echo "   curl $API_URL/transcripts/$TEST_USER"
fi

# Test 6: Check transcripts (immediate check, likely empty)
echo -e "\n📍 Test 6: Checking transcripts for user: $TEST_USER"
curl -s "$API_URL/transcripts/$TEST_USER" | python3 -m json.tool
echo ""

echo -e "\n✅ API tests completed!"
echo "================================================"
echo ""
echo "To monitor the batch processor, check the logs:"
echo "  - Local: Check terminal output"
echo "  - Docker: docker-compose logs -f"
echo ""
echo "To manually check transcripts later:"
echo "  curl $API_URL/transcripts/$TEST_USER"