import glob
import logging
import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

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


# Get transcripts for a user
@app.get("/transcripts/{uid}")
async def get_transcripts(uid: str, limit: int = Query(10, ge=1, le=100)):
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
    logger.info(f"Environment variables - CI: {os.environ.get('CI')}, GITHUB_ACTIONS: {os.environ.get('GITHUB_ACTIONS')}")
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
