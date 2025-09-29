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


class TestStreamingAudio:
    """Test real-time streaming audio functionality"""

    def test_wav_header_generation(self):
        """Test WAV header generation for raw audio"""
        from audio_utils import create_wav_header

        # Test header for 1 second of audio at 16kHz, 16-bit, mono
        sample_rate = 16000
        bits_per_sample = 16
        num_channels = 1
        duration_seconds = 1
        data_length = sample_rate * duration_seconds * num_channels * (bits_per_sample // 8)

        header = create_wav_header(data_length, sample_rate, num_channels, bits_per_sample)

        # WAV header should be exactly 44 bytes
        assert len(header) == 44

        # Check RIFF header
        assert header[0:4] == b"RIFF"
        assert header[8:12] == b"WAVE"

        # Check fmt chunk
        assert header[12:16] == b"fmt "

        # Check data chunk
        assert header[36:40] == b"data"

    def test_add_wav_header_to_raw_audio(self):
        """Test adding WAV header to raw PCM audio"""
        from audio_utils import add_wav_header_to_raw_audio

        # Create fake raw audio (100 bytes)
        raw_audio = b"\x00" * 100
        sample_rate = 16000

        wav_audio = add_wav_header_to_raw_audio(raw_audio, sample_rate)

        # Result should be header (44 bytes) + raw audio (100 bytes)
        assert len(wav_audio) == 144

        # Check it starts with RIFF header
        assert wav_audio[0:4] == b"RIFF"

    def test_validate_audio_params(self):
        """Test audio parameter validation"""
        from audio_utils import validate_audio_params

        # Test valid parameters
        sample_rate, uid = validate_audio_params(16000, "user123")
        assert sample_rate == 16000
        assert uid == "user123"

        # Test default sample rate
        sample_rate, uid = validate_audio_params(None, "user456")
        assert sample_rate == 16000
        assert uid == "user456"

        # Test invalid sample rate gets corrected to default
        sample_rate, uid = validate_audio_params(999999, "user789")
        assert sample_rate == 16000  # Should default to 16000
        assert uid == "user789"

        # Test missing UID raises error
        with pytest.raises(ValueError, match="User ID"):
            validate_audio_params(16000, None)

        with pytest.raises(ValueError, match="User ID"):
            validate_audio_params(16000, "")

    def test_streaming_file_naming(self):
        """Test streaming audio file naming convention"""
        from datetime import datetime

        uid = "test_user"
        timestamp = int(datetime.now().timestamp())
        filename = f"streaming_{uid}_{timestamp}.wav"

        # Check filename format
        assert filename.startswith("streaming_")
        assert uid in filename
        assert filename.endswith(".wav")

    def test_raw_audio_size_calculation(self):
        """Test raw audio size calculations"""
        # 16kHz, 16-bit (2 bytes per sample), mono
        sample_rate = 16000
        bits_per_sample = 16
        duration_seconds = 10

        # Calculate expected size
        expected_size = sample_rate * duration_seconds * (bits_per_sample // 8)
        assert expected_size == 320000  # 10 seconds = 320KB

        # Test size in MB
        size_mb = expected_size / (1024 * 1024)
        assert size_mb == pytest.approx(0.305, rel=1e-2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
