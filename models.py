from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from config import config

Base = declarative_base()

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True)
    uid = Column(String(100), index=True)
    audio_filename = Column(String(255))
    transcript_text = Column(Text)
    duration_seconds = Column(Float)
    cost_usd = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, default=datetime.utcnow)

# Ensure directories exist before creating database
os.makedirs(os.path.dirname(config.TRANSCRIPT_DB), exist_ok=True)

# Database setup
engine = create_engine(f"sqlite:///{config.TRANSCRIPT_DB}")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()