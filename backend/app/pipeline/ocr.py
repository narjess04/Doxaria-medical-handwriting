"""OCR imprimé de secours (Tesseract), pour les zones courtes : cachet, numéro de bulletin.

Optionnel : si Tesseract n'est pas installé, `disponible()` renvoie False et les
étapes qui en dépendent sont sautées (et signalées dans la réponse).
"""

import re
from functools import lru_cache

from PIL import Image, ImageOps


@lru_cache(maxsize=1)
def disponible() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()  # lève une erreur si le programme est introuvable
        return True
    except Exception:
        return False


def _prepare(image: Image.Image) -> Image.Image:
    # Les petites zones se lisent mieux agrandies et en niveaux de gris.
    image = ImageOps.grayscale(image)
    if image.height < 60:
        image = image.resize((image.width * 60 // max(image.height, 1), 60), Image.BICUBIC)
    return ImageOps.autocontrast(image)


def lire(image: Image.Image) -> str | None:
    """Texte de la zone (français), ou None si Tesseract est indisponible."""
    if not disponible():
        return None
    import pytesseract

    return " ".join(pytesseract.image_to_string(_prepare(image), lang="fra+eng", config="--psm 6").split())


def lire_chiffres(image: Image.Image) -> str | None:
    if not disponible():
        return None
    import pytesseract

    brut = pytesseract.image_to_string(_prepare(image), config="--psm 7 -c tessedit_char_whitelist=0123456789")
    return re.sub(r"\D", "", brut) or None
