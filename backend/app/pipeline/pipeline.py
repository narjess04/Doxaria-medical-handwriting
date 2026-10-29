"""Orchestration : image -> type de document -> extraction adaptée."""

import re

from PIL import Image

from app.chatbot.referentiels import medicaments_dans
from app.core import config

from . import bulletin, classification, correction, detection, lecture_api, modeles, recognition
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


# Lignes d'en-tête du médecin dans le texte brut de Mistral OCR.
_ENTETE = re.compile(r"\b(dr|docteur|pr|professeur|m[ée]decin|sp[ée]cialiste|cabinet|t[ée]l|fax|ancien interne)\b", re.I)


def _ranger_par_mots_cles(lignes: list[str]) -> dict:
    """Texte brut (Mistral OCR) -> date (1re date valide), en-tête du médecin, prescription."""
    entete, date_lue, corps = [], None, []
    for brut in lignes:
        if date_lue is None and correction.normaliser_date(brut):
            date_lue = correction.normaliser_date(brut)
        elif _ENTETE.search(brut):
            entete.append(brut)
        else:
            corps.append(brut)
    return {"medecin": " · ".join(entete) or None, "date": date_lue, "patient": None, "prescription": corps}


def lire_ordonnance_api(image: Image.Image) -> dict:
    """Page entière lue par API, en un appel : le modèle de vision range lui-même médecin,
    date, patient et prescription (plus fiable que les zones YOLO) ; avec Mistral OCR, le
    rangement se fait par mots-clés. La prescription est ensuite corrigée avec le référentiel.
    L'API ne renvoie pas la position des lignes : pas de cadres à dessiner (`champs` vide).
    """
    if lecture_api.vision():
        lu = lecture_api.lire_ordonnance(image)
    else:
        lu = _ranger_par_mots_cles(lecture_api.lire_page(image))
    texte = "\n".join(correction.corriger(l)[0] for l in lu["prescription"])
    date = correction.normaliser_date(lu["date"]) if lu["date"] else None
    return {"medecin": lu["medecin"], "date": date or lu["date"], "patient": lu["patient"], "texte": texte,
            "champs": [], "medicaments": sorted({m["nom"] for m in medicaments_dans(texte)}),
            "modele": lecture_api.nom_modele()}


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
        return {**commun, "lecture": True, "numero": None, **lire_ordonnance_api(image)}
    except ModeleIndisponible:
        pass  # pas de clé d'API, ou API injoignable : lecture locale par TrOCR
    try:
        return {**commun, "lecture": True, "numero": None, **lire_ordonnance(image)}
    except ModeleIndisponible:
        if not modeles.present(config.MODELE_LIGNES):
            raise
        return {**commun, "lecture": False, "medecin": None, "date": None, "texte": "", "numero": None,
                "champs": detection.lignes(image), "medicaments": [], "modele": None}
