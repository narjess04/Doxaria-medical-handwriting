"""Point d'entrée de l'API : uvicorn main:app --reload --port 8000"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core import config

app = FastAPI(title="Doxaria API", version="0.1.0",
              description="Assistant médical (RAG) et vérification des médicaments ; pipeline OCR à venir.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["*"])
app.include_router(router)
