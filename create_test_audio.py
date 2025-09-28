#!/usr/bin/env python3
import wave
import math
import struct

# Create a simple WAV file with a 440Hz tone
def create_test_wav(filename="test_audio.wav", duration=3, frequency=440, sample_rate=16000):
    # Calculate number of frames
    n_frames = int(sample_rate * duration)

    # Generate sine wave data
    amplitude = 16384  # Half of max for 16-bit audio
    data = []
    for i in range(n_frames):
        value = amplitude * math.sin(2.0 * math.pi * frequency * i / sample_rate)
        data.append(struct.pack('<h', int(value)))  # 16-bit little-endian

    # Create WAV file
    with wave.open(filename, 'wb') as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 2 bytes per sample (16-bit)
        wav.setframerate(sample_rate)
        wav.writeframes(b''.join(data))

    print(f"✅ Created {filename} - {duration}s @ {sample_rate}Hz")

if __name__ == "__main__":
    create_test_wav()