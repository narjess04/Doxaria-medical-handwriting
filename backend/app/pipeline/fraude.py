"""Détection de fraude sur une ordonnance.

Reprise de la logique de l'ancienne version, corrigée :
1. YOLOv8 cherche la zone « docteur » (en-tête) et le cachet (« stamp »).
2. Pas de cachet, ou pas d'en-tête médecin : document suspect.
3. Si un OCR est disponible, on vérifie que le cachet porte bien le nom du
   médecin de l'en-tête. L'ancienne version acceptait n'importe quel mot en
   commun (similarité TF-IDF > 1 %) ; ici on mesure la part des mots de
   l'en-tête retrouvés dans le cachet, en tolérant les erreurs d'OCR.
"""

import difflib
import re
import unicodedata

from PIL import Image

from app.core import config

from . import detection, ocr
from .preprocessing import recadrer

# Mots trop courants sur un en-tête pour identifier un médecin.
MOTS_VIDES = {"DOCTEUR", "DR", "MEDECIN", "MEDECINE", "GENERALE", "SPECIALISTE", "TEL", "FAX", "RUE", "AVENUE",
              "TUNIS", "TUNISIE", "CABINET", "DIPLOME", "FACULTE", "ANCIEN", "INTERNE", "HOPITAUX", "DES", "LES"}


def _mots(texte: str) -> set[str]:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().upper()
    return {m for m in re.findall(r"[A-Z]{3,}", texte) if m not in MOTS_VIDES}


def correspondance(texte_docteur: str, texte_cachet: str) -> float:
    """Part des mots de l'en-tête retrouvés dans le cachet (0 à 1), à une faute d'OCR près."""
    docteur, cachet = _mots(texte_docteur), _mots(texte_cachet)
    if not docteur or not cachet:
        return 0.0
    trouves = sum(1 for m in docteur if difflib.get_close_matches(m, cachet, n=1, cutoff=0.8))
    return trouves / len(docteur)


def analyser(image: Image.Image) -> dict:
    """{verdict: conforme|suspect, message, score, details}. Le score est la probabilité de fraude estimée."""
    boites = detection.detecter(config.MODELE_FRAUDE, image)
    docteur, cachet = detection.meilleure(boites, "docteur"), detection.meilleure(boites, "stamp")
    details = {
        "cachet": cachet["confiance"] if cachet else None,
        "entete_medecin": docteur["confiance"] if docteur else None,
        "correspondance": None,
        "ocr": ocr.disponible(),
        "boites": boites,
    }

    if not cachet:
        return {"verdict": "suspect", "score": 0.9, "details": details,
                "message": "Aucun cachet détecté sur le document."}
    if not docteur:
        return {"verdict": "suspect", "score": 0.7, "details": details,
                "message": "Cachet présent, mais aucun en-tête de médecin détecté."}

    texte_docteur = ocr.lire(recadrer(image, docteur["bbox"]))
    texte_cachet = ocr.lire(recadrer(image, cachet["bbox"]))
    if texte_docteur is None or texte_cachet is None:
        # Sans OCR, on ne peut contrôler que la présence des éléments.
        score = round(1 - min(cachet["confiance"], docteur["confiance"]), 2)
        return {"verdict": "conforme", "score": score, "details": details,
                "message": "Cachet et en-tête du médecin présents. Comparaison des noms non effectuée "
                           "(OCR non installé sur le serveur)."}

    sim = round(correspondance(texte_docteur, texte_cachet), 2)
    details["correspondance"] = sim
    if sim >= config.SEUIL_SIMILARITE_CACHET:
        return {"verdict": "conforme", "score": round(1 - sim, 2), "details": details,
                "message": f"Le cachet correspond au médecin de l'en-tête ({sim:.0%} des mots retrouvés)."}
    return {"verdict": "suspect", "score": round(1 - sim, 2), "details": details,
            "message": "Le cachet ne correspond pas au médecin de l'en-tête."}
