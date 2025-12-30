import glob
import logging
import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from audio_utils import add_wav_header_to_raw_audio, validate_audio_params
from config import config
from r2_storage import R2Storage
from transcription import transcription_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate configuration on startup
config.validate()

# Initialize FastAPI
app = FastAPI(title="OMI Transcription Service", version="1.0.0")

# Initialize scheduler for batch processing
scheduler = AsyncIOScheduler()

# Initialize R2 storage
r2_storage = R2Storage(config)

# API Key Authentication
API_KEY = os.getenv("API_KEY")


async def verify_api_key(request: Request):
    """Verify API key for protected endpoints."""
    if not API_KEY:
        return None

    api_key = request.headers.get("X-API-Key")
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": config.ENVIRONMENT,
        "r2_bucket": config.R2_BUCKET_NAME,
    }


# Receive audio from OMI device
@app.post("/audio")
async def receive_audio(
    file: UploadFile = File(...),
    uid: str = Query(..., description="User ID"),
    sample_rate: int | None = Query(16000, description="Sample rate"),  # noqa: ARG001
    _api_key: str | None = Depends(verify_api_key),
):
    """
    Receive audio from OMI device and queue for processing
    """
    try:
        # Generate unique filename
        timestamp = int(datetime.now().timestamp())
        filename = f"audio_{uid}_{timestamp}.wav"
        filepath = os.path.join(config.AUDIO_QUEUE_DIR, filename)

        # Save audio file
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        # Calculate file size
        file_size_mb = len(content) / (1024 * 1024)

        logger.info(f"Received audio from {uid}: {filename} ({file_size_mb:.2f}MB)")

        return JSONResponse(
            content={
                "status": "queued",
                "uid": uid,
                "filename": filename,
                "size_mb": round(file_size_mb, 2),
                "message": f"Audio queued for processing. Will be transcribed within {config.BATCH_DURATION_SECONDS} seconds.",
            }
        )

    except Exception as e:
        logger.error(f"Error receiving audio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Receive real-time streaming audio from OMI device
@app.post("/streaming")
async def receive_streaming_audio(
    request: Request,
    uid: str | None = Query(None, description="User ID"),
    sample_rate: int | None = Query(None, description="Sample rate"),
    _api_key: str | None = Depends(verify_api_key),
):
    """
    Receive raw audio bytes from OMI device real-time streaming.
    OMI sends raw PCM audio without WAV headers as octet-stream.
    """
    # Log incoming request details
    logger.info("=" * 60)
    logger.info(f"[STREAMING] Incoming request from {request.client.host}")
    logger.info(f"[STREAMING] Query params - uid: {uid}, sample_rate: {sample_rate}")
    logger.info(f"[STREAMING] Content-Type: {request.headers.get('content-type', 'not specified')}")

    try:
        # Validate parameters
        sample_rate, uid = validate_audio_params(sample_rate, uid)
        logger.info(f"[STREAMING] Validated params - uid: {uid}, sample_rate: {sample_rate}")

        # Read raw audio bytes
        raw_audio = await request.body()
        raw_audio_size = len(raw_audio)
        logger.info(f"[STREAMING] Received {raw_audio_size} raw audio bytes from OMI device")

        if not raw_audio:
            logger.warning("[STREAMING] No audio data received - empty request body")
            raise HTTPException(status_code=400, detail="No audio data received")

        # Add WAV header to raw audio
        wav_audio = add_wav_header_to_raw_audio(raw_audio, sample_rate)
        logger.info(f"[STREAMING] Added WAV header - total size now {len(wav_audio)} bytes")

        # Generate unique filename
        timestamp = int(datetime.now().timestamp())
        filename = f"streaming_{uid}_{timestamp}.wav"
        filepath = os.path.join(config.AUDIO_QUEUE_DIR, filename)
        logger.info(f"[STREAMING] Generated filename: {filename}")

        # Save WAV file for batch processing
        with open(filepath, "wb") as f:
            f.write(wav_audio)
        logger.info(f"[STREAMING] ✅ Successfully saved audio file to: {filepath}")

        # Calculate file size
        file_size_mb = len(wav_audio) / (1024 * 1024)

        # Calculate approximate audio duration (16kHz, 16-bit mono)
        audio_duration_seconds = raw_audio_size / (16000 * 2)  # 2 bytes per sample

        logger.info(f"[STREAMING] File details - Size: {file_size_mb:.2f}MB, Duration: ~{audio_duration_seconds:.1f}s")
        logger.info(f"[STREAMING] Audio queued for transcription - will process in {config.BATCH_DURATION_SECONDS}s")
        logger.info("=" * 60)

        return JSONResponse(
            content={
                "status": "queued",
                "uid": uid,
                "filename": filename,
                "size_mb": round(file_size_mb, 2),
                "sample_rate": sample_rate,
                "raw_bytes_received": len(raw_audio),
                "message": f"Streaming audio received and queued. Will be transcribed within {config.BATCH_DURATION_SECONDS} seconds.",
            }
        )

    except ValueError as e:
        logger.error(f"Validation error in streaming: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error receiving streaming audio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Get transcripts for a user
@app.get("/transcripts/{uid}")
async def get_transcripts(
    uid: str,
    limit: int = Query(10, ge=1, le=100),
    _api_key: str | None = Depends(verify_api_key),
):
    """
    Get transcripts for a specific user from R2
    """
    try:
        transcripts = r2_storage.list_user_transcripts(uid, limit)

        return {
            "uid": uid,
            "count": len(transcripts),
            "transcripts": [
                {
                    "text": t.get("transcript_text"),
                    "filename": t.get("audio_filename"),
                    "cost": t.get("cost_usd"),
                    "created_at": t.get("created_at"),
                    "duration_seconds": t.get("duration_seconds"),
                    "r2_key": t.get("r2_key"),
                }
                for t in transcripts
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching transcripts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Get usage statistics
@app.get("/stats")
async def get_stats():
    """
    Get usage statistics and cost information from R2
    """
    try:
        # Calculate stats for current month
        now = datetime.utcnow()

        # Get stats from R2
        month_stats = r2_storage.get_stats(month=now.month, year=now.year)

        # Get queue status
        queue_files = len(glob.glob(f"{config.AUDIO_QUEUE_DIR}/*.wav"))

        # Test R2 connection
        r2_connected = r2_storage.test_connection()

        return {
            "environment": config.ENVIRONMENT,
            "r2_bucket": config.R2_BUCKET_NAME,
            "r2_connected": r2_connected,
            "current_month": {
                "files_processed": month_stats["total_files"],
                "total_cost_usd": month_stats["total_cost_usd"],
                "storage_cost_usd": month_stats["storage_cost_usd"],
                "total_size_mb": month_stats["total_size_mb"],
                "estimated_monthly_cost": round(month_stats["total_cost_usd"] * 30 / now.day, 2) if now.day > 0 else 0,
            },
            "queue": {"pending_files": queue_files, "next_batch_in_seconds": config.BATCH_DURATION_SECONDS},
            "config": {
                "batch_duration_seconds": config.BATCH_DURATION_SECONDS,
                "max_batch_size_mb": config.MAX_BATCH_SIZE_MB,
                "groq_model": config.GROQ_MODEL,
                "cost_per_hour": transcription_service.cost_per_hour,
            },
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task to process audio batches
async def process_audio_batch():
    """Background task to process queued audio"""
    logger.info("Starting batch processing...")
    try:
        results = await transcription_service.process_batch()
        if results:
            logger.info(f"Processed {len(results)} files, total cost: ${sum(r['cost'] for r in results):.4f}")
    except Exception as e:
        logger.error(f"Batch processing error: {str(e)}")


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize background tasks"""
    # Log environment details for debugging
    logger.info("=" * 60)
    logger.info("Application starting up...")
    logger.info(
        f"Environment variables - CI: {os.environ.get('CI')}, GITHUB_ACTIONS: {os.environ.get('GITHUB_ACTIONS')}"
    )
    logger.info(f"Config - ENVIRONMENT: {config.ENVIRONMENT}, BUCKET: {config.R2_BUCKET_NAME}")
    logger.info(f"Python version: {os.sys.version}")
    logger.info("=" * 60)

    # Schedule batch processing
    scheduler.add_job(
        process_audio_batch,
        "interval",
        seconds=config.BATCH_DURATION_SECONDS,
        id="batch_processor",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Batch processor scheduled to run every {config.BATCH_DURATION_SECONDS} seconds")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    scheduler.shutdown()
    logger.info("Scheduler shut down")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
