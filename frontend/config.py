"""Configuration du frontend Flask."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Variables locales (SECRET_KEY, BACKEND_URL…) : frontend/.env, jamais versionné.
# La clé du modèle de langage est dans backend/.env.
load_dotenv(Path(__file__).resolve().parent / ".env")


class Config:
    # En production, définir SECRET_KEY dans l'environnement.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-cle-a-changer")
    # Par défaut : SQLite dans frontend/instance/ (voir create_app).
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("HTTPS", "0") == "1"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    # API du pipeline OCR (backend/). S'il ne répond pas : mode démonstration.
    BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 Mo par image
