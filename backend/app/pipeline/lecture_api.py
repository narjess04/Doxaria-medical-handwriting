"""Lecture d'une ordonnance entière par une API, en un seul appel par document.

- Modèle de vision (config.OCR_MODEL, via OpenRouter) : lit la page et range lui-même
  le texte en médecin, date, patient et prescription (réponse JSON) ;
- Mistral OCR : texte seul ; le rangement se fait ensuite par mots-clés (pipeline).

Sans clé, `disponible()` renvoie False et la lecture retombe sur TrOCR.
"""

import base64
import io
import json
import re

import requests
from PIL import Image

from app.core import config

from .modeles import ModeleIndisponible

CONSIGNE = """Tu lis une ordonnance médicale tunisienne (souvent manuscrite, en français, parfois avec de l'arabe).
Recopie fidèlement ce qui est écrit, sans rien inventer ni corriger. Réponds uniquement avec ce JSON :
{"medecin": "nom, spécialité et coordonnées du médecin (en-tête et cachet), ou null",
 "date": "date de l'ordonnance telle qu'écrite, ou null",
 "patient": "nom du patient, ou null",
 "prescription": ["une ligne par médicament ou consigne, avec dosage et posologie"],
 "texte": "tout le texte de la page, ligne par ligne"}"""


def vision() -> bool:
    return bool(config.OCR_API_KEY)


def disponible() -> bool:
    return vision() or bool(config.MISTRAL_API_KEY)


def nom_modele() -> str:
    return config.OCR_MODEL if vision() else f"Mistral OCR ({config.MISTRAL_OCR_MODEL})"


def _data_uri(image: Image.Image) -> str:
    # JPEG : bien plus léger que PNG pour une photo de document.
    tampon = io.BytesIO()
    image.convert("RGB").save(tampon, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(tampon.getvalue()).decode()


def _post(url: str, cle: str, corps: dict) -> dict:
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {cle}"}, json=corps, timeout=config.OCR_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        raise ModeleIndisponible(f"Lecture par API indisponible : {e}") from e


def _texte(valeur) -> str | None:
    return " ".join(str(valeur).split()) or None if valeur else None


def lire_ordonnance(image: Image.Image) -> dict:
    """{medecin, date, patient, prescription: [lignes]} lus par le modèle de vision."""
    reponse = _post(f"{config.OCR_BASE_URL}/chat/completions", config.OCR_API_KEY, {
        "model": config.OCR_MODEL, "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": CONSIGNE},
            {"type": "image_url", "image_url": {"url": _data_uri(image)}}]}],
    })
    try:
        contenu = reponse["choices"][0]["message"]["content"]
        # Le JSON peut être entouré de ```json … ``` : on garde ce qui est entre les accolades.
        donnees = json.loads(contenu[contenu.index("{"):contenu.rindex("}") + 1])
    except (KeyError, IndexError, ValueError, TypeError) as e:
        raise ModeleIndisponible("Réponse illisible du modèle de vision.") from e
    lignes = donnees.get("prescription") or []
    if isinstance(lignes, str):
        lignes = lignes.splitlines()
    return {"medecin": _texte(donnees.get("medecin")), "date": _texte(donnees.get("date")),
            "patient": _texte(donnees.get("patient")), "prescription": [l for l in map(_texte, lignes) if l]}


def _lignes(markdown: str) -> list[str]:
    """Markdown renvoyé par Mistral -> lignes de texte brut (sans #, *, |, images)."""
    lignes = []
    for ligne in markdown.splitlines():
        ligne = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", ligne)  # images incrustées
        ligne = re.sub(r"^\s*(#+|[-*+]|\d+\.)\s+", "", ligne)  # titres, puces
        ligne = re.sub(r"[*_`]|^\||\|$", "", ligne.strip()).replace("|", " ")
        ligne = " ".join(ligne.split())
        if ligne and not re.fullmatch(r"[-:\s]+", ligne):  # séparateurs de tableau
            lignes.append(ligne)
    return lignes


def lire_page(image: Image.Image) -> list[str]:
    """Lignes lues par Mistral OCR, dans l'ordre de lecture (une page facturée)."""
    if not config.MISTRAL_API_KEY:
        raise ModeleIndisponible("Clé Mistral absente (MISTRAL_API_KEY dans backend/.env).")
    reponse = _post("https://api.mistral.ai/v1/ocr", config.MISTRAL_API_KEY, {
        "model": config.MISTRAL_OCR_MODEL, "document": {"type": "image_url", "image_url": _data_uri(image)}})
    return [l for page in reponse.get("pages", []) for l in _lignes(page.get("markdown", ""))]
