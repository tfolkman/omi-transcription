"""
Audio utilities for handling OMI real-time streaming audio.
Includes WAV header generation for raw PCM audio bytes.
"""

import struct


def create_wav_header(
    data_length: int, sample_rate: int = 16000, num_channels: int = 1, bits_per_sample: int = 16
) -> bytes:
    """
    Generate a WAV header for raw PCM audio data.

    This is needed because OMI sends raw audio bytes without headers.
    We need to add WAV headers to make the audio processable by transcription services.

    Args:
        data_length: Length of the raw audio data in bytes
        sample_rate: Sample rate in Hz (default: 16000 for OMI devices)
        num_channels: Number of audio channels (default: 1 for mono)
        bits_per_sample: Bits per sample (default: 16)

    Returns:
        44-byte WAV header as bytes
    """
    # Calculate derived values
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8

    # Create the 44-byte WAV header
    header = bytearray(44)

    # RIFF chunk descriptor
    header[0:4] = b"RIFF"
    struct.pack_into("<I", header, 4, 36 + data_length)  # ChunkSize
    header[8:12] = b"WAVE"

    # fmt sub-chunk
    header[12:16] = b"fmt "
    struct.pack_into("<I", header, 16, 16)  # Subchunk1Size (16 for PCM)
    struct.pack_into("<H", header, 20, 1)  # AudioFormat (1 for PCM)
    struct.pack_into("<H", header, 22, num_channels)
    struct.pack_into("<I", header, 24, sample_rate)
    struct.pack_into("<I", header, 28, byte_rate)
    struct.pack_into("<H", header, 32, block_align)
    struct.pack_into("<H", header, 34, bits_per_sample)

    # data sub-chunk
    header[36:40] = b"data"
    struct.pack_into("<I", header, 40, data_length)

    return bytes(header)


def add_wav_header_to_raw_audio(raw_audio: bytes, sample_rate: int = 16000) -> bytes:
    """
    Add a WAV header to raw PCM audio bytes from OMI device.

    Args:
        raw_audio: Raw PCM audio bytes from OMI
        sample_rate: Sample rate in Hz (default: 16000)

    Returns:
        Complete WAV file as bytes (header + audio data)
    """
    header = create_wav_header(len(raw_audio), sample_rate)
    return header + raw_audio


def validate_audio_params(sample_rate: int | None, uid: str | None) -> tuple[int, str]:
    """
    Validate and set default values for audio streaming parameters.

    Args:
        sample_rate: Sample rate from request (can be None)
        uid: User ID from request (can be None)

    Returns:
        Tuple of (sample_rate, uid) with defaults applied

    Raises:
        ValueError: If uid is missing or invalid
    """
    # Default sample rate for OMI devices
    if sample_rate is None:
        sample_rate = 16000

    # Validate sample rate is reasonable
    if sample_rate not in [8000, 16000, 22050, 44100, 48000]:
        # Log warning but use default
        sample_rate = 16000

    # UID is required
    if not uid:
        raise ValueError("User ID (uid) is required")

    return sample_rate, uid
