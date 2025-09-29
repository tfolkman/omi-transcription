#!/usr/bin/env python3
"""
Test script for OMI real-time streaming functionality.
Simulates an OMI device sending raw audio bytes to the streaming endpoint.
"""

import asyncio
import sys
from pathlib import Path

import httpx
import numpy as np

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from audio_utils import create_wav_header


def generate_test_audio(duration_seconds: float = 5, sample_rate: int = 16000) -> bytes:
    """
    Generate test PCM audio data (sine wave).
    This simulates raw audio bytes from an OMI device.
    """
    frequency = 440  # A4 note
    samples = int(duration_seconds * sample_rate)

    # Generate sine wave
    t = np.linspace(0, duration_seconds, samples, False)
    audio_data = np.sin(frequency * 2 * np.pi * t)

    # Convert to 16-bit PCM
    audio_data = (audio_data * 32767).astype(np.int16)

    # Return as raw bytes (no WAV header, like OMI sends)
    return audio_data.tobytes()


def save_test_wav(raw_audio: bytes, filename: str = "test_generated.wav", sample_rate: int = 16000):
    """Save raw audio with WAV header for verification."""
    header = create_wav_header(len(raw_audio), sample_rate)
    with open(filename, "wb") as f:
        f.write(header + raw_audio)
    print(f"✓ Saved test audio to {filename}")


async def test_streaming_endpoint(
    base_url: str = "http://localhost:8000",
    uid: str = "test_user_123",
    sample_rate: int = 16000,
    duration_seconds: float = 5,
):
    """
    Test the /streaming endpoint by sending raw audio bytes.
    """
    print("\n🎤 Testing OMI Streaming Endpoint")
    print(f"   URL: {base_url}/streaming")
    print(f"   User ID: {uid}")
    print(f"   Sample Rate: {sample_rate} Hz")
    print(f"   Duration: {duration_seconds} seconds\n")

    # Generate test audio (raw PCM, no headers)
    print(f"1. Generating {duration_seconds}s of test audio...")
    raw_audio = generate_test_audio(duration_seconds, sample_rate)
    audio_size_kb = len(raw_audio) / 1024
    print(f"   Generated {len(raw_audio)} bytes ({audio_size_kb:.1f} KB) of raw PCM audio")

    # Save for verification
    save_test_wav(raw_audio, sample_rate=sample_rate)

    # Send to streaming endpoint
    print("\n2. Sending raw audio to streaming endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            # Send as octet-stream (like OMI does)
            response = await client.post(
                f"{base_url}/streaming",
                params={"uid": uid, "sample_rate": sample_rate},
                content=raw_audio,
                headers={"Content-Type": "application/octet-stream"},
            )

            if response.status_code == 200:
                result = response.json()
                print("   ✅ Success! Response:")
                print(f"      Status: {result.get('status')}")
                print(f"      Filename: {result.get('filename')}")
                print(f"      Size: {result.get('size_mb')} MB")
                print(f"      Raw bytes received: {result.get('raw_bytes_received')}")
                print(f"      Message: {result.get('message')}")

                return result
            else:
                print(f"   ❌ Error {response.status_code}: {response.text}")
                return None

        except httpx.ConnectError:
            print(f"   ❌ Could not connect to {base_url}")
            print("      Make sure the server is running: python app.py")
            return None
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            return None


async def test_multiple_chunks(
    base_url: str = "http://localhost:8000",
    uid: str = "test_user_multi",
    num_chunks: int = 3,
    chunk_duration: float = 2,
):
    """
    Test sending multiple audio chunks, simulating real-time streaming.
    """
    print("\n🎯 Testing Multiple Streaming Chunks")
    print(f"   Sending {num_chunks} chunks of {chunk_duration}s each")

    for i in range(num_chunks):
        print(f"\n   Chunk {i + 1}/{num_chunks}:")
        result = await test_streaming_endpoint(base_url=base_url, uid=uid, duration_seconds=chunk_duration)

        if result:
            print(f"   ✓ Chunk {i + 1} sent successfully")
        else:
            print(f"   ✗ Chunk {i + 1} failed")
            break

        # Wait between chunks (simulating real-time intervals)
        if i < num_chunks - 1:
            wait_time = 5
            print(f"   Waiting {wait_time}s before next chunk...")
            await asyncio.sleep(wait_time)


async def verify_transcripts(base_url: str = "http://localhost:8000", uid: str = "test_user_123"):
    """
    Check if transcripts were created for the test user.
    """
    print(f"\n📝 Checking Transcripts for {uid}...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/transcripts/{uid}")

            if response.status_code == 200:
                result = response.json()
                count = result.get("count", 0)
                print(f"   Found {count} transcript(s)")

                if count > 0:
                    for i, transcript in enumerate(result.get("transcripts", []), 1):
                        print(f"\n   Transcript {i}:")
                        print(f"      Filename: {transcript.get('filename')}")
                        print(f"      Created: {transcript.get('created_at')}")
                        print(f"      Duration: {transcript.get('duration_seconds')}s")
                        print(f"      Cost: ${transcript.get('cost', 0):.4f}")
                        text = transcript.get("text", "")
                        if text:
                            preview = text[:100] + "..." if len(text) > 100 else text
                            print(f"      Text: {preview}")
            else:
                print(f"   Error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"   Error: {str(e)}")


async def main():
    """
    Main test function.
    """
    print("=" * 60)
    print("OMI REAL-TIME STREAMING TEST")
    print("=" * 60)

    base_url = "http://localhost:8000"

    # Test 1: Single audio chunk
    result = await test_streaming_endpoint(base_url=base_url)

    if result:
        # Test 2: Multiple chunks (simulating real streaming)
        await test_multiple_chunks(base_url=base_url)

        # Wait for batch processing
        print("\n⏱️  Waiting 30s for batch processing to start...")
        await asyncio.sleep(30)

        # Test 3: Verify transcripts
        await verify_transcripts(base_url=base_url, uid="test_user_123")
        await verify_transcripts(base_url=base_url, uid="test_user_multi")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
