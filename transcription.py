import os
import glob
import asyncio
from typing import List, Dict
from groq import Groq
from datetime import datetime
import logging
from config import config
from models import Transcript, get_db

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.cost_per_hour = 0.04  # whisper-large-v3-turbo

    async def process_batch(self) -> List[Dict]:
        """Process all queued audio files"""
        results = []
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
                name_without_ext = filename.replace('.wav', '')
                # Split only at the first and last underscore to handle UIDs with underscores
                parts = name_without_ext.split('_')
                if len(parts) >= 3 and parts[0] == 'audio':
                    # Join all parts except first (audio) and last (timestamp)
                    uid = '_'.join(parts[1:-1])
                else:
                    uid = 'unknown'

                # Get file size for cost calculation
                file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)

                # Skip if file is too large
                if file_size_mb > config.MAX_BATCH_SIZE_MB:
                    logger.warning(f"File {filename} is too large ({file_size_mb:.2f}MB), skipping")
                    continue

                # Transcribe with Groq
                with open(audio_path, 'rb') as audio_file:
                    start_time = datetime.now()

                    transcription = self.client.audio.transcriptions.create(
                        file=(filename, audio_file.read()),
                        model=config.GROQ_MODEL,
                        language="en",
                        temperature=0.0,
                        response_format="json"
                    )

                    processing_time = (datetime.now() - start_time).total_seconds()

                # Calculate cost (estimate 2 minutes of audio per file)
                estimated_minutes = 2
                cost = (estimated_minutes / 60) * self.cost_per_hour

                # Save to database
                db = next(get_db())
                transcript = Transcript(
                    uid=uid,
                    audio_filename=filename,
                    transcript_text=transcription.text,
                    duration_seconds=processing_time,
                    cost_usd=cost
                )
                db.add(transcript)
                db.commit()

                # Delete processed audio file
                os.remove(audio_path)

                results.append({
                    'uid': uid,
                    'filename': filename,
                    'transcript': transcription.text,
                    'cost': cost,
                    'processing_time': processing_time
                })

                logger.info(f"Successfully processed {filename}")

            except Exception as e:
                logger.error(f"Error processing {audio_path}: {str(e)}")
                # Don't delete file on error, try again next batch

        return results

transcription_service = TranscriptionService()