import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    # Batching settings
    BATCH_DURATION_SECONDS = int(os.getenv("BATCH_DURATION_SECONDS", 120))
    MAX_BATCH_SIZE_MB = int(os.getenv("MAX_BATCH_SIZE_MB", 20))

    # Paths - use local paths for development, Docker paths for production
    if os.path.exists("/.dockerenv"):
        # Running in Docker
        AUDIO_QUEUE_DIR = "/app/data/audio_queue"
        TRANSCRIPT_DB = "/app/data/transcripts.db"
    else:
        # Running locally
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DATA_DIR = os.path.join(BASE_DIR, "data")
        AUDIO_QUEUE_DIR = os.path.join(DATA_DIR, "audio_queue")
        TRANSCRIPT_DB = os.path.join(DATA_DIR, "transcripts.db")

    # Server settings
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "0.0.0.0")

    # Groq settings
    GROQ_MODEL = "whisper-large-v3-turbo"

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required")

        # Create directories if they don't exist
        os.makedirs(cls.AUDIO_QUEUE_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(cls.TRANSCRIPT_DB), exist_ok=True)

config = Config()