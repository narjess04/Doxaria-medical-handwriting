"""Routes HTTP de l'API.

GET  /api/health                  état du service, du modèle de langage et des modèles de vision
POST /api/chat                    assistant médical (RAG)
POST /api/medicaments/verifier    médicaments du référentiel cités dans un texte
GET  /api/referentiels/stats      taille des référentiels
POST /api/classify                type de document (CNN)
POST /api/extract                 lecture d'une ordonnance ou d'un bulletin de soins
POST /api/fraud                   détection de fraude (cachet / en-tête du médecin)
"""

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.chatbot import rag
from app.chatbot.referentiels import medicaments_dans, statistiques
from app.pipeline import classification, fraude, modeles, ocr, pipeline
from app.pipeline.modeles import ModeleIndisponible
from app.pipeline.preprocessing import ImageInvalide, charger_image

from .schemas import (ChatReponse, ChatRequete, Classification, Extraction, Fraude, Statistiques, TexteRequete,
                      Verification)

router = APIRouter(prefix="/api")


def image_envoyee(fichier: UploadFile):
    try:
        return charger_image(fichier.file.read())
    except ImageInvalide as e:
        raise HTTPException(422, str(e)) from e


@router.get("/health")
def health():
    return {"status": "ok", "llm": rag.llm_configure(), "ocr": ocr.disponible(), "modeles": modeles.disponibles()}


@router.post("/chat", response_model=ChatReponse, response_model_exclude_none=True)
def chat(req: ChatRequete):
    historique = [m.model_dump() for m in req.historique[-8:]]
    return rag.repondre(req.question.strip(), historique)


@router.post("/medicaments/verifier", response_model=Verification)
def verifier(req: TexteRequete):
    # Un même médicament cité deux fois n'apparaît qu'une fois.
    trouves = {m["nom"]: m for m in medicaments_dans(req.texte)}
    return {"medicaments": list(trouves.values())}


@router.get("/referentiels/stats", response_model=Statistiques)
def stats():
    return statistiques()


@router.post("/classify", response_model=Classification)
def classify(image: UploadFile = File(...)):
    try:
        type_document, confiance = classification.classer(image_envoyee(image))
    except ModeleIndisponible as e:
        raise HTTPException(501, str(e)) from e
    return {"type": type_document, "confiance": confiance}


@router.post("/extract", response_model=Extraction)
def extract(image: UploadFile = File(...),
            type: Literal["auto", "ordonnance", "bulletin"] = Form("auto")):
    try:
        return pipeline.extraire(image_envoyee(image), type)
    except ModeleIndisponible as e:
        raise HTTPException(501, {"message": str(e), "type": type if type != "auto" else "ordonnance"}) from e


@router.post("/fraud", response_model=Fraude)
def fraud(image: UploadFile = File(...)):
    try:
        return fraude.analyser(image_envoyee(image))
    except ModeleIndisponible as e:
        raise HTTPException(501, str(e)) from e
