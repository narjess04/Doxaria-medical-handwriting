"""Orchestration : image -> type de document -> extraction adaptée."""

from PIL import Image

from app.chatbot.referentiels import medicaments_dans
from app.core import config

from . import bulletin, classification, correction, detection, recognition
from .modeles import ModeleIndisponible
from .preprocessing import recadrer

TYPES = ("ordonnance", "bulletin")


def _centre_dans(b, zone, marge=0.1):
    """Le centre de la boîte b tombe-t-il dans la zone (agrandie de `marge`) ?"""
    if zone is None:
        return False
    x0, y0, x1, y1 = zone["bbox"]
    mx, my = (x1 - x0) * marge, (y1 - y0) * marge
    cx, cy = (b["bbox"][0] + b["bbox"][2]) / 2, (b["bbox"][1] + b["bbox"][3]) / 2
    return x0 - mx <= cx <= x1 + mx and y0 - my <= cy <= y1 + my


def _zone(chemin, image, classe):
    """Meilleure boîte d'une classe, ou None si le modèle manque (étape facultative)."""
    try:
        return detection.meilleure(detection.detecter(chemin, image), classe)
    except ModeleIndisponible:
        return None


def lire_ordonnance(image: Image.Image) -> dict:
    """Lignes lues par TrOCR, réparties entre en-tête du médecin, date et prescription.

    - en-tête : lignes dans la zone « docteur » du modèle de fraude ;
    - date : lignes dans la zone « date » du modèle date/texte (sinon, la zone est lue à part) ;
    - prescription : le reste, corrigé avec le référentiel des médicaments et des termes médicaux.
    """
    boites = detection.lignes(image)
    zone_docteur = _zone(config.MODELE_FRAUDE, image, "docteur")
    zone_date = _zone(config.MODELE_DATE, image, "date")
    textes = recognition.lire_lignes([recadrer(image, b["bbox"]) for b in boites])

    entete, date_lue, corps, champs = [], None, [], []
    for b, brut in zip(boites, textes):
        if not brut:
            continue
        if _centre_dans(b, zone_date) and correction.normaliser_date(brut):
            role, corrige = "date", brut
            date_lue = date_lue or correction.normaliser_date(brut)
        elif _centre_dans(b, zone_docteur):
            role, corrige = "medecin", brut
            entete.append(brut)
        else:
            role = "prescription"
            corrige, _ = correction.corriger(brut)
            corps.append(corrige)
        champs.append({**b, "classe": role, "texte": corrige, "libelle": brut if brut != corrige else None})

    if date_lue is None and zone_date is not None:
        # La date n'est pas tombée dans une ligne détectée : on lit sa zone directement.
        date_lue = correction.normaliser_date(recognition.lire_lignes([recadrer(image, zone_date["bbox"])])[0])

    texte = "\n".join(corps)
    return {"medecin": " · ".join(entete) or None, "date": date_lue, "texte": texte, "champs": champs,
            "medicaments": sorted({m["nom"] for m in medicaments_dans(texte)}), "modele": recognition.nom_modele()}


def extraire(image: Image.Image, type_document: str = "auto") -> dict:
    """{type, confiance_type, lecture, medecin, date, texte, numero, champs, medicaments, modele, largeur, hauteur}.

    `type_document` : "ordonnance", "bulletin", ou "auto" (choisi par le CNN).
    `lecture` vaut False quand les lignes sont détectées mais ne peuvent pas être lues
    (TrOCR indisponible) : `champs` contient alors les lignes.
    """
    confiance = None
    if type_document not in TYPES:
        type_document, confiance = classification.classer(image)
    commun = {"type": type_document, "confiance_type": confiance, "largeur": image.width, "hauteur": image.height}

    if type_document == "bulletin":
        res = bulletin.analyser(image)
        return {**commun, "lecture": True, "medecin": None, "date": None, "texte": res["texte"],
                "numero": res["numero"], "champs": res["champs"], "medicaments": [], "modele": None}

    try:
        return {**commun, "lecture": True, "numero": None, **lire_ordonnance(image)}
    except ModeleIndisponible:
        if not config.MODELE_LIGNES.exists():
            raise
        return {**commun, "lecture": False, "medecin": None, "date": None, "texte": "", "numero": None,
                "champs": detection.lignes(image), "medicaments": [], "modele": None}
