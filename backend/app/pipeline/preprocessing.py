"""Prétraitement des images de documents."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core import config

# Une photo de téléphone dépasse rarement 12 Mpx ; au-delà, on réduit (mémoire, vitesse).
COTE_MAX = 4000


class ImageInvalide(ValueError):
    pass


def charger_image(donnees: bytes) -> Image.Image:
    """Image RGB, remise à l'endroit, à partir des octets envoyés."""
    if not donnees:
        raise ImageInvalide("Fichier vide.")
    if len(donnees) > config.TAILLE_MAX_IMAGE:
        raise ImageInvalide("Image trop volumineuse (10 Mo maximum).")
    try:
        image = Image.open(io.BytesIO(donnees))
        image.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ImageInvalide("Le fichier n'est pas une image lisible.") from e
    # Les photos de téléphone sont souvent stockées couchées, avec l'orientation dans l'EXIF.
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > COTE_MAX:
        image.thumbnail((COTE_MAX, COTE_MAX))
    return image


def recadrer(image: Image.Image, bbox, marge=6) -> Image.Image:
    """Découpe une boîte (x0, y0, x1, y1) avec une petite marge, sans sortir de l'image."""
    x0, y0, x1, y1 = bbox
    w, h = image.size
    return image.crop((max(0, int(x0) - marge), max(0, int(y0) - marge),
                       min(w, int(x1) + marge), min(h, int(y1) + marge)))
