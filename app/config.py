"""
Application Configuration Module for DataPulse.
Loads environment variables and sets up database and security settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from the project root if it exists
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration loaded in all environments."""

    # Secret key for signing session cookies and CSRF tokens
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-datapulse-2026-change-in-prod")

    # Max upload file size: 16 Megabytes (16 * 1024 * 1024 bytes)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # Database connection URL
    # Supabase provides URLs like: postgresql://postgres.[REF]:[PASS]@[HOST]:[PORT]/postgres
    # Sometimes cloud providers use `postgres://`, which SQLAlchemy 1.4+ rejects in favor of `postgresql://`
    raw_db_url = os.environ.get("DATABASE_URL", "").strip()

    if raw_db_url:
        if raw_db_url.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = raw_db_url.replace("postgres://", "postgresql://", 1)
        else:
            SQLALCHEMY_DATABASE_URI = raw_db_url
        IS_SUPABASE_CONFIGURED = True
    else:
        # Graceful fallback to local SQLite for offline development before Supabase is connected
        local_db_path = BASE_DIR / "datapulse_local.db"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{local_db_path}"
        IS_SUPABASE_CONFIGURED = False

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Serverless-friendly SQLAlchemy engine configuration:
    # pool_pre_ping: tests if connection is alive before issuing queries (avoids stale connection errors)
    # pool_recycle: recycles idle connections before Supabase or Vercel drops them
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Google Sheets Integration Settings (for Phase 3)
    GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()


class DevelopmentConfig(Config):
    """Development environment specific settings."""
    DEBUG = True


class ProductionConfig(Config):
    """Production (Vercel) environment specific settings."""
    DEBUG = False


class TestingConfig(Config):
    """Testing environment settings (uses in-memory SQLite)."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


# Map config names to classes
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
