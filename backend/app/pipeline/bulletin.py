"""Lecture d'un bulletin de soins CNAM : champs détectés et numéro de bulletin."""

from PIL import Image

from app.core import config

from . import detection, ocr
from .preprocessing import recadrer

# Classes du modèle YOLOv8 de l'ancienne version -> libellés affichés.
CHAMPS = {
    "num_bulletin": "Numéro de bulletin",
    "cnam": "Logo CNAM",
    "adher": "Zone adhérent",
    "nom_adherent": "Nom de l'adhérent",
    "cin": "CIN",
    "date_nai": "Date de naissance",
    "patient": "Zone patient",
    "tab1": "Tableau des actes",
    "signa": "Signature",
}


def analyser(image: Image.Image) -> dict:
    """{numero, champs: [{classe, libelle, confiance, bbox}], manquants, texte}."""
    boites = detection.detecter(config.MODELE_BULLETIN, image)
    # Une boîte par champ : la plus confiante.
    champs = {}
    for b in boites:
        champs.setdefault(b["classe"], {**b, "libelle": CHAMPS.get(b["classe"], b["classe"])})

    numero = None
    if "num_bulletin" in champs:
        numero = ocr.lire_chiffres(recadrer(image, champs["num_bulletin"]["bbox"]))

    manquants = [libelle for classe, libelle in CHAMPS.items() if classe not in champs]
    lignes = ["Bulletin de soins CNAM"]
    lignes.append(f"Numéro : {numero}" if numero else
                  "Numéro : non lu" + ("" if ocr.disponible() else " (OCR non installé sur le serveur)"))
    lignes.append("Éléments détectés : " + (", ".join(c["libelle"] for c in champs.values()) or "aucun"))
    if manquants:
        lignes.append("Éléments absents : " + ", ".join(manquants))
    return {"numero": numero, "champs": list(champs.values()), "manquants": manquants, "texte": "\n".join(lignes)}
