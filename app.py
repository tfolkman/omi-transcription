from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import glob
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

from config import config
from models import Transcript, get_db
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

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Receive audio from OMI device
@app.post("/audio")
async def receive_audio(
    file: UploadFile = File(...),
    uid: str = Query(..., description="User ID"),
    sample_rate: Optional[int] = Query(16000, description="Sample rate")
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
        with open(filepath, 'wb') as f:
            f.write(content)

        # Calculate file size
        file_size_mb = len(content) / (1024 * 1024)

        logger.info(f"Received audio from {uid}: {filename} ({file_size_mb:.2f}MB)")

        return JSONResponse(content={
            "status": "queued",
            "uid": uid,
            "filename": filename,
            "size_mb": round(file_size_mb, 2),
            "message": f"Audio queued for processing. Will be transcribed within {config.BATCH_DURATION_SECONDS} seconds."
        })

    except Exception as e:
        logger.error(f"Error receiving audio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get transcripts for a user
@app.get("/transcripts/{uid}")
async def get_transcripts(
    uid: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get transcripts for a specific user
    """
    transcripts = db.query(Transcript)\
        .filter(Transcript.uid == uid)\
        .order_by(Transcript.created_at.desc())\
        .limit(limit)\
        .all()

    return {
        "uid": uid,
        "count": len(transcripts),
        "transcripts": [
            {
                "id": t.id,
                "text": t.transcript_text,
                "filename": t.audio_filename,
                "cost": t.cost_usd,
                "created_at": t.created_at.isoformat(),
                "duration_seconds": t.duration_seconds
            }
            for t in transcripts
        ]
    }

# Get usage statistics
@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    Get usage statistics and cost information
    """
    # Calculate stats for current month
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    month_transcripts = db.query(Transcript)\
        .filter(Transcript.created_at >= month_start)\
        .all()

    total_cost = sum(t.cost_usd for t in month_transcripts)
    total_files = len(month_transcripts)

    # Get queue status
    queue_files = len(glob.glob(f"{config.AUDIO_QUEUE_DIR}/*.wav"))

    return {
        "current_month": {
            "files_processed": total_files,
            "total_cost_usd": round(total_cost, 4),
            "estimated_monthly_cost": round(total_cost * 30 / now.day, 2) if now.day > 0 else 0
        },
        "queue": {
            "pending_files": queue_files,
            "next_batch_in_seconds": config.BATCH_DURATION_SECONDS
        },
        "config": {
            "batch_duration_seconds": config.BATCH_DURATION_SECONDS,
            "max_batch_size_mb": config.MAX_BATCH_SIZE_MB,
            "groq_model": config.GROQ_MODEL,
            "cost_per_hour": transcription_service.cost_per_hour
        }
    }

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
    # Schedule batch processing
    scheduler.add_job(
        process_audio_batch,
        'interval',
        seconds=config.BATCH_DURATION_SECONDS,
        id='batch_processor',
        replace_existing=True
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