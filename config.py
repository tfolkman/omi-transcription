import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")  # dev or prod

    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    # Cloudflare R2 Configuration
    R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    # Bucket name can be explicitly set or auto-selected based on environment
    R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME") or ("omi-dev" if ENVIRONMENT in ["dev", "development"] else "omi")

    # Batching settings
    BATCH_DURATION_SECONDS = int(os.getenv("BATCH_DURATION_SECONDS", 120))
    MAX_BATCH_SIZE_MB = int(os.getenv("MAX_BATCH_SIZE_MB", 20))

    # Paths - use local paths for development, Docker paths for production
    if os.path.exists("/.dockerenv"):
        # Running in Docker
        AUDIO_QUEUE_DIR = "/app/data/audio_queue"
    else:
        # Running locally
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DATA_DIR = os.path.join(BASE_DIR, "data")
        AUDIO_QUEUE_DIR = os.path.join(DATA_DIR, "audio_queue")

    # Server settings
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "0.0.0.0")  # nosec B104 - Binding to all interfaces is required for containerized deployment

    # Groq settings
    GROQ_MODEL = "whisper-large-v3-turbo"

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required")

        if not cls.R2_ACCOUNT_ID:
            raise ValueError("R2_ACCOUNT_ID is required")

        if not cls.R2_ACCESS_KEY_ID:
            raise ValueError("R2_ACCESS_KEY_ID is required")

        if not cls.R2_SECRET_ACCESS_KEY:
            raise ValueError("R2_SECRET_ACCESS_KEY is required")

        # Create directories if they don't exist
        os.makedirs(cls.AUDIO_QUEUE_DIR, exist_ok=True)


config = Config()
