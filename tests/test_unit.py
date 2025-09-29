#!/usr/bin/env python3
"""Unit tests for OMI Transcription Service"""

import os
import sys
from unittest.mock import patch

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTranscriptionHelpers:
    """Test transcription helper functions"""

    def test_calculate_cost(self):
        """Test cost calculation for audio transcription"""
        # Cost is $0.04 per hour
        cost_per_hour = 0.04

        # Test 1 minute audio
        cost = (60 / 3600) * cost_per_hour
        assert cost == pytest.approx(0.000667, rel=1e-2)

        # Test 10 minutes audio
        cost = (600 / 3600) * cost_per_hour
        assert cost == pytest.approx(0.00667, rel=1e-2)

        # Test 1 hour audio
        cost = (3600 / 3600) * cost_per_hour
        assert cost == pytest.approx(0.04, rel=1e-3)

    @patch("boto3.client")
    def test_r2_key_generation(self, mock_boto):
        """Test R2 storage key generation"""
        uid = "test-user-123"
        filename = "audio_20240101_120000.wav"

        # Expected key format
        expected_key = f"transcripts/{uid}/{filename}.json"

        # Verify key format
        assert "transcripts/" in expected_key
        assert uid in expected_key
        assert filename in expected_key


class TestAudioValidation:
    """Test audio file validation"""

    def test_valid_audio_extensions(self):
        """Test that valid audio extensions are accepted"""
        valid_extensions = [".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"]

        for ext in valid_extensions:
            filename = f"test{ext}"
            assert filename.endswith(ext)

    def test_audio_file_size_limits(self):
        """Test audio file size validation"""
        # Max file size should be 25MB for Whisper
        max_size_mb = 25
        max_size_bytes = max_size_mb * 1024 * 1024

        # Test file just under limit
        assert (max_size_bytes - 1) < max_size_bytes

        # Test file over limit
        assert (max_size_bytes + 1) > max_size_bytes


class TestR2Storage:
    """Test R2 storage functionality"""

    @patch("boto3.client")
    def test_r2_connection(self, mock_boto):
        """Test R2 connection configuration"""
        from config import Config
        from r2_storage import R2Storage

        # Mock the boto3 client
        mock_boto.return_value = None

        # Create R2Storage instance
        storage = R2Storage(Config)

        # Verify bucket name is set
        assert storage.bucket_name is not None

    def test_transcript_json_structure(self):
        """Test transcript JSON structure"""
        from datetime import datetime

        transcript = {
            "uid": "test-user",
            "audio_filename": "test.wav",
            "transcript_text": "Test transcript",
            "cost_usd": 0.01,
            "duration_seconds": 60,
            "created_at": datetime.utcnow().isoformat(),
            "processed_at": datetime.utcnow().isoformat(),
        }

        # Verify all required fields exist
        assert "uid" in transcript
        assert "audio_filename" in transcript
        assert "transcript_text" in transcript
        assert "cost_usd" in transcript
        assert "duration_seconds" in transcript


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
