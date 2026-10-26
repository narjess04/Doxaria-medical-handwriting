"""Chargement des modèles, une seule fois et à la première utilisation.

PyTorch et Ultralytics ne sont importés qu'ici et seulement au besoin : l'API
démarre même s'ils sont absents (l'assistant et les référentiels n'en ont pas besoin).
"""

import threading
from functools import lru_cache
from pathlib import Path

from app.core import config


class ModeleIndisponible(RuntimeError):
    pass


# L'inférence n'est pas garantie thread-safe : un verrou par modèle.
_verrous: dict[str, threading.Lock] = {}


def verrou(nom: str) -> threading.Lock:
    return _verrous.setdefault(nom, threading.Lock())


def _verifie(chemin: Path):
    if not chemin.exists():
        raise ModeleIndisponible(f"Modèle absent : {chemin.relative_to(config.BACKEND_DIR)}")


@lru_cache(maxsize=None)
def yolo(chemin: Path):
    _verifie(chemin)
    try:
        from ultralytics import YOLO
    except ImportError as e:
        raise ModeleIndisponible("Ultralytics n'est pas installé (pip install ultralytics).") from e
    return YOLO(str(chemin))


@lru_cache(maxsize=1)
def cnn():
    _verifie(config.MODELE_CLASSIFICATION)
    try:
        import torch
    except ImportError as e:
        raise ModeleIndisponible("PyTorch n'est pas installé.") from e
    from .classification import OrdonnanceClassifierCNN

    modele = OrdonnanceClassifierCNN()
    # weights_only : le fichier ne contient que des tenseurs, rien d'exécutable n'est chargé.
    modele.load_state_dict(torch.load(config.MODELE_CLASSIFICATION, map_location="cpu", weights_only=True))
    return modele.eval()


def disponibles() -> dict[str, bool]:
    """Modèles présents sur le disque (pour /api/health)."""
    return {
        "classification": config.MODELE_CLASSIFICATION.exists(),
        "fraude": config.MODELE_FRAUDE.exists(),
        "bulletin": config.MODELE_BULLETIN.exists(),
        "lignes": config.MODELE_LIGNES.exists(),
        "trocr": (config.MODELE_TROCR / "config.json").exists(),
    }
