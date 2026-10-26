"""Reconnaissance du texte manuscrit avec TrOCR.

- Modèle fine-tuné (notebook 02) s'il est dans backend/models/trocr-doxaria/ ;
- sinon, TrOCR pré-entraîné sur l'écriture manuscrite (config.TROCR_SECOURS),
  téléchargé une seule fois dans le cache Hugging Face. Il ne connaît ni le
  français médical ni les noms de médicaments : la correction par le
  référentiel (module correction) rattrape une partie des erreurs.
"""

import importlib.util
from functools import lru_cache

from PIL import Image

from app.core import config

from . import modeles


def fine_tune() -> bool:
    return (config.MODELE_TROCR / "config.json").exists()


def disponible() -> bool:
    return importlib.util.find_spec("transformers") is not None


def nom_modele() -> str:
    return "TrOCR fine-tuné (Doxaria)" if fine_tune() else f"TrOCR pré-entraîné ({config.TROCR_SECOURS})"


@lru_cache(maxsize=1)
def _charger():
    if not disponible():
        raise modeles.ModeleIndisponible("transformers n'est pas installé (pip install transformers).")
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    source = config.MODELE_TROCR if fine_tune() else config.TROCR_SECOURS
    try:
        processor = TrOCRProcessor.from_pretrained(source)
        modele = VisionEncoderDecoderModel.from_pretrained(source).eval()
    except OSError as e:  # pas de réseau au premier téléchargement, dossier incomplet…
        raise modeles.ModeleIndisponible(f"Impossible de charger {source} : {e}") from e
    return processor, modele


def lire_lignes(images: list[Image.Image], num_beams: int = config.TROCR_FAISCEAUX, lot: int = 8) -> list[str]:
    """Une transcription par image de ligne (traitées par lots pour limiter la mémoire)."""
    if not images:
        return []
    import torch

    processor, modele = _charger()
    textes = []
    for i in range(0, len(images), lot):
        pixel_values = processor(images=[im.convert("RGB") for im in images[i:i + lot]], return_tensors="pt").pixel_values
        with modeles.verrou("trocr"), torch.inference_mode():
            sortie = modele.generate(pixel_values=pixel_values, num_beams=num_beams, max_new_tokens=64)
        textes += [" ".join(t.split()) for t in processor.batch_decode(sortie, skip_special_tokens=True)]
    return textes
