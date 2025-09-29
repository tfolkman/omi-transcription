import glob
import logging
import os
from datetime import datetime

from groq import Groq

from config import config
from r2_storage import R2Storage

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.cost_per_hour = 0.04  # whisper-large-v3-turbo
        self.r2_storage = R2Storage(config)

    async def process_batch(self) -> list[dict]:
        """Process all queued audio files"""
        results: list[dict] = []
        audio_files = glob.glob(f"{config.AUDIO_QUEUE_DIR}/*.wav")

        if not audio_files:
            logger.info("No audio files to process")
            return results

        logger.info(f"Processing {len(audio_files)} audio files")

        for audio_path in audio_files:
            try:
                # Extract metadata from filename (format: audio_UID_TIMESTAMP.wav)
                filename = os.path.basename(audio_path)
                # Remove .wav extension and split
                name_without_ext = filename.replace(".wav", "")
                # Split only at the first and last underscore to handle UIDs with underscores
                parts = name_without_ext.split("_")
                if len(parts) >= 3 and parts[0] == "audio":
                    # Join all parts except first (audio) and last (timestamp)
                    uid = "_".join(parts[1:-1])
                    timestamp = int(parts[-1])
                else:
                    uid = "unknown"
                    timestamp = int(datetime.now().timestamp())

                # Get file size for cost calculation
                file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)

                # Skip if file is too large
                if file_size_mb > config.MAX_BATCH_SIZE_MB:
                    logger.warning(f"File {filename} is too large ({file_size_mb:.2f}MB), skipping")
                    continue

                # Transcribe with Groq
                with open(audio_path, "rb") as audio_file:
                    start_time = datetime.now()

                    transcription = self.client.audio.transcriptions.create(
                        file=(filename, audio_file.read()),
                        model=config.GROQ_MODEL,
                        language="en",
                        temperature=0.0,
                        response_format="json",
                    )

                    processing_time = (datetime.now() - start_time).total_seconds()

                # Calculate cost (estimate 2 minutes of audio per file)
                estimated_minutes = 2
                cost = (estimated_minutes / 60) * self.cost_per_hour

                # Create transcript data object
                transcript_data = {
                    "uid": uid,
                    "timestamp": timestamp,
                    "audio_filename": filename,
                    "transcript_text": transcription.text,
                    "duration_seconds": processing_time,
                    "cost_usd": cost,
                    "created_at": datetime.utcnow().isoformat(),
                    "processed_at": datetime.utcnow().isoformat(),
                    "file_size_mb": file_size_mb,
                    "groq_model": config.GROQ_MODEL,
                }

                # Save to R2
                r2_key = self.r2_storage.save_transcript(transcript_data)

                if r2_key:
                    # Delete processed audio file only if successfully saved to R2
                    os.remove(audio_path)

                    results.append(
                        {
                            "uid": uid,
                            "filename": filename,
                            "transcript": transcription.text,
                            "cost": cost,
                            "processing_time": processing_time,
                            "r2_key": r2_key,
                        }
                    )

                    logger.info(f"Successfully processed {filename} and saved to R2: {r2_key}")
                else:
                    logger.error(f"Failed to save {filename} to R2, keeping audio file")

            except Exception as e:
                logger.error(f"Error processing {audio_path}: {str(e)}")
                # Don't delete file on error, try again next batch

        return results


transcription_service = TranscriptionService()
