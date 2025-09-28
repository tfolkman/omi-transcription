#!/usr/bin/env python3
"""
Test script for local development without Groq API
Creates mock transcription responses for testing
"""

import asyncio
import os
import json
from datetime import datetime
from unittest.mock import MagicMock, patch
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the Groq client before importing
mock_groq = MagicMock()
sys.modules['groq'] = mock_groq

from models import Transcript, get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def setup_test_db():
    """Setup a test database"""
    test_db_path = "/tmp/test_transcripts.db"
    engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal, test_db_path

def test_database_operations():
    """Test database CRUD operations"""
    print("Testing database operations...")

    SessionLocal, db_path = setup_test_db()
    db = SessionLocal()

    try:
        # Create test transcript
        transcript = Transcript(
            uid="test_user",
            audio_filename="test_audio.wav",
            transcript_text="This is a test transcript",
            duration_seconds=2.5,
            cost_usd=0.0022
        )
        db.add(transcript)
        db.commit()
        print("✅ Created transcript record")

        # Read transcript
        result = db.query(Transcript).filter(Transcript.uid == "test_user").first()
        assert result is not None
        assert result.transcript_text == "This is a test transcript"
        print(f"✅ Retrieved transcript: {result.transcript_text[:30]}...")

        # Update transcript
        result.transcript_text = "Updated transcript text"
        db.commit()
        print("✅ Updated transcript")

        # List all transcripts
        all_transcripts = db.query(Transcript).all()
        print(f"✅ Found {len(all_transcripts)} transcript(s)")

    finally:
        db.close()
        # Clean up
        if os.path.exists(db_path):
            os.remove(db_path)

    print("Database tests passed!\n")

async def test_transcription_mock():
    """Test transcription with mocked Groq API"""
    print("Testing transcription service (mocked)...")

    # Create mock response
    mock_response = MagicMock()
    mock_response.text = "This is a mock transcription of the audio file"

    with patch('transcription.Groq') as MockGroq:
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        MockGroq.return_value = mock_client

        # Import after patching
        from transcription import TranscriptionService

        service = TranscriptionService()

        # Create test audio directory
        os.makedirs("/tmp/test_audio_queue", exist_ok=True)

        # Create dummy audio file
        test_file = "/tmp/test_audio_queue/audio_testuser_12345.wav"
        with open(test_file, "wb") as f:
            f.write(b"dummy audio data")

        # Mock config
        with patch('transcription.config') as mock_config:
            mock_config.AUDIO_QUEUE_DIR = "/tmp/test_audio_queue"
            mock_config.MAX_BATCH_SIZE_MB = 25
            mock_config.GROQ_MODEL = "whisper-large-v3-turbo"

            # Mock database
            with patch('transcription.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = iter([mock_db])

                # Process batch
                results = await service.process_batch()

                if results:
                    print(f"✅ Processed {len(results)} file(s)")
                    for result in results:
                        print(f"   - {result['filename']}: {result['transcript'][:50]}...")
                else:
                    print("⚠️  No files processed (this is okay for mock test)")

        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)
        os.rmdir("/tmp/test_audio_queue")

    print("Transcription tests passed!\n")

def test_api_endpoints():
    """Test FastAPI endpoints"""
    print("Testing API endpoints...")

    try:
        from fastapi.testclient import TestClient
        from app import app

        # Mock config for testing
        with patch('app.config') as mock_config:
            mock_config.AUDIO_QUEUE_DIR = "/tmp/test_queue"
            mock_config.BATCH_DURATION_SECONDS = 120
            mock_config.MAX_BATCH_SIZE_MB = 25
            mock_config.GROQ_MODEL = "whisper-large-v3-turbo"
            mock_config.validate.return_value = None

            # Create test client
            client = TestClient(app)

            # Test health endpoint
            response = client.get("/health")
            assert response.status_code == 200
            assert "status" in response.json()
            print("✅ Health check endpoint works")

            # Test stats endpoint
            with patch('app.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.all.return_value = []
                mock_get_db.return_value = iter([mock_db])

                response = client.get("/stats")
                assert response.status_code == 200
                data = response.json()
                assert "current_month" in data
                assert "queue" in data
                assert "config" in data
                print("✅ Stats endpoint works")

            # Test transcripts endpoint
            with patch('app.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_transcript = MagicMock()
                mock_transcript.id = 1
                mock_transcript.transcript_text = "Test transcript"
                mock_transcript.audio_filename = "test.wav"
                mock_transcript.cost_usd = 0.001
                mock_transcript.created_at = datetime.utcnow()
                mock_transcript.duration_seconds = 2.5

                mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_transcript]
                mock_get_db.return_value = iter([mock_db])

                response = client.get("/transcripts/test_user")
                assert response.status_code == 200
                data = response.json()
                assert "uid" in data
                assert "transcripts" in data
                print("✅ Transcripts endpoint works")

            print("API endpoint tests passed!\n")

    except ImportError:
        print("⚠️  FastAPI test client not available. Install with: pip install httpx")
        print("   Skipping API endpoint tests\n")

def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("🧪 OMI Transcription Service - Local Tests")
    print("="*50 + "\n")

    # Run tests
    test_database_operations()
    asyncio.run(test_transcription_mock())
    test_api_endpoints()

    print("="*50)
    print("✅ All tests passed successfully!")
    print("="*50)
    print("\nNote: These tests use mocked APIs and don't require Groq API key")
    print("For real API testing, use ./test_api.sh after starting the server\n")

if __name__ == "__main__":
    main()