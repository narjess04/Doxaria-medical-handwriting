"""Chargement des modèles, une seule fois et à la première utilisation.

Deux formats pour chaque modèle (CNN, YOLOv8) :
- .onnx, exécuté par onnxruntime (~50 Mo) : utilisé dès qu'il existe, c'est le
  format du serveur en ligne (voir scripts/exporter_onnx.py) ;
- .pt, exécuté par PyTorch / Ultralytics (plus de 1 Go), pour l'entraînement en local.
Les bibliothèques ne sont importées qu'au besoin : l'API démarre même si elles sont
absentes (l'assistant et les référentiels n'en ont pas besoin).
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


def version_onnx(chemin: Path) -> Path | None:
    """Le .onnx à côté du .pt, s'il existe."""
    onnx = chemin.with_suffix(".onnx")
    return onnx if onnx.exists() else None


def present(chemin: Path) -> bool:
    return chemin.exists() or version_onnx(chemin) is not None


@lru_cache(maxsize=None)
def session_onnx(chemin: Path):
    _verifie(chemin)
    try:
        import onnxruntime
    except ImportError as e:
        raise ModeleIndisponible("onnxruntime n'est pas installé (pip install onnxruntime).") from e
    return onnxruntime.InferenceSession(str(chemin), providers=["CPUExecutionProvider"])


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
        "classification": present(config.MODELE_CLASSIFICATION),
        "fraude": present(config.MODELE_FRAUDE),
        "bulletin": present(config.MODELE_BULLETIN),
        "lignes": present(config.MODELE_LIGNES),
        "trocr": (config.MODELE_TROCR / "config.json").exists(),
    }
