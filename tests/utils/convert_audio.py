#!/usr/bin/env python3
"""
Convert M4A to WAV format for testing
Uses pydub library which can handle various audio formats
"""

import os
import sys


def convert_m4a_to_wav_simple(input_file, output_file):
    """
    Try to convert using system tools if available
    """
    import subprocess

    # Try ffmpeg first
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                input_file,
                "-ar",
                "16000",  # 16kHz sample rate
                "-ac",
                "1",  # Mono
                "-y",  # Overwrite
                output_file,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"✅ Converted using ffmpeg: {output_file}")
            return True
    except FileNotFoundError:
        pass

    # Try afconvert (macOS)
    try:
        result = subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", input_file, output_file],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"✅ Converted using afconvert: {output_file}")
            return True
    except FileNotFoundError:
        pass

    print("❌ Neither ffmpeg nor afconvert available")
    print("   Install ffmpeg: brew install ffmpeg")
    return False


def try_pydub_conversion(input_file, output_file):
    """
    Try using pydub if available
    """
    try:
        from pydub import AudioSegment

        # Load M4A file
        audio = AudioSegment.from_file(input_file, "m4a")

        # Convert to mono and 16kHz
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)

        # Export as WAV
        audio.export(output_file, format="wav")
        print(f"✅ Converted using pydub: {output_file}")
        return True
    except ImportError:
        print("⚠️  pydub not installed. Trying system tools...")
        return False
    except Exception as e:
        print(f"❌ pydub conversion failed: {e}")
        return False


if __name__ == "__main__":
    input_m4a = "tests/fixtures/test.m4a"
    output_wav = "tests/fixtures/test_speech.wav"

    if not os.path.exists(input_m4a):
        print(f"❌ Input file not found: {input_m4a}")
        sys.exit(1)

    # Try pydub first, then fall back to system tools
    success = try_pydub_conversion(input_m4a, output_wav)

    if not success:
        success = convert_m4a_to_wav_simple(input_m4a, output_wav)

    if success and os.path.exists(output_wav):
        # Check file size
        size_bytes = os.path.getsize(output_wav)
        print(f"📊 WAV file size: {size_bytes / 1024:.1f} KB")
    else:
        print("❌ Conversion failed")
        sys.exit(1)
