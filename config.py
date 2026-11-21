"""Application settings, read from environment variables.

Copy .env.example for a full list. Values marked "required in production" must be set
before running with CLINIC_ENV=production; the app refuses to start otherwise.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"


def _env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = os.environ.get("CLINIC_ENV", "development")  # "development" or "production"
    CLINIC_NAME = os.environ.get("CLINIC_NAME", "Sunrise Medical Clinic")
    CLINIC_ADDRESS = os.environ.get("CLINIC_ADDRESS", "Hauptstraße 1, 12345 Musterstadt")
    CLINIC_TZ = os.environ.get("CLINIC_TZ", "Europe/Berlin")
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

    INSTANCE_DIR = INSTANCE_DIR
    DATABASE = os.environ.get("CLINIC_DB", str(INSTANCE_DIR / "clinic.db"))

    SECRET_KEY = os.environ.get("SECRET_KEY", "")                 # required in production
    ENCRYPTION_KEY = os.environ.get("CLINIC_ENCRYPTION_KEY", "")  # required in production (Fernet key)

    RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "90"))
    SESSION_RETENTION_HOURS = int(os.environ.get("SESSION_RETENTION_HOURS", "24"))

    # (allowed requests, window in seconds) per client IP
    RATE_CHAT = (30, 60)
    RATE_BOOKING = (10, 60)
    RATE_LOGIN = (5, 900)

    SMTP_HOST = os.environ.get("SMTP_HOST", "")  # empty = write emails to instance/outbox
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "appointments@example.com")

    SESSION_COOKIE_NAME = "clinic_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)  # set true behind HTTPS

    @classmethod
    def check_production(cls):
        if cls.APP_ENV != "production":
            return
        missing = [
            name
            for name, value in (("SECRET_KEY", cls.SECRET_KEY), ("CLINIC_ENCRYPTION_KEY", cls.ENCRYPTION_KEY))
            if not value
        ]
        if missing:
            raise RuntimeError(f"Required settings missing for production: {', '.join(missing)}")