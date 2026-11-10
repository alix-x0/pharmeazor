import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Ensure the data directory exists
os.makedirs(settings.DATA_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{settings.DATA_DIR}/medsafe.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
