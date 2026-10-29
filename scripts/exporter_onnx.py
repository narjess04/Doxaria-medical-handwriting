"""Convertit les poids PyTorch (.pt) du backend au format ONNX (.onnx), à côté des originaux.

Le serveur en ligne n'a alors besoin que d'onnxruntime (~50 Mo) au lieu de PyTorch et
Ultralytics (plus de 1 Go). Le backend utilise le .onnx dès qu'il existe.

Lancer depuis la racine du dépôt, avec le Python du backend (PyTorch, Ultralytics et onnx installés) :
    backend\\.venv\\Scripts\\python scripts/exporter_onnx.py
"""

import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "backend"))

from app.core import config  # noqa: E402
from app.pipeline import classification  # noqa: E402

YOLO = [config.MODELE_FRAUDE, config.MODELE_BULLETIN, config.MODELE_DATE, config.MODELE_LIGNES]


def exporter_cnn():
    import torch

    modele = classification.OrdonnanceClassifierCNN()
    modele.load_state_dict(torch.load(config.MODELE_CLASSIFICATION, map_location="cpu", weights_only=True))
    entree = torch.zeros(1, 3, classification.TAILLE, classification.TAILLE)
    sortie = config.MODELE_CLASSIFICATION.with_suffix(".onnx")
    torch.onnx.export(modele.eval(), entree, sortie, input_names=["image"], output_names=["logits"],
                      dynamic_axes={"image": {0: "lot"}}, dynamo=False)
    print("CNN ->", sortie.relative_to(RACINE))


def exporter_yolo(chemin: Path):
    from ultralytics import YOLO as Yolo

    # Taille fixe (celle de l'entraînement) ; noms des classes gardés dans les métadonnées du .onnx.
    fichier = Path(Yolo(str(chemin)).export(format="onnx", imgsz=640, simplify=False, dynamic=False))
    if fichier != chemin.with_suffix(".onnx"):
        shutil.move(fichier, chemin.with_suffix(".onnx"))
    print("YOLO ->", chemin.with_suffix(".onnx").relative_to(RACINE))


if __name__ == "__main__":
    exporter_cnn()
    for chemin in YOLO:
        if chemin.exists():
            exporter_yolo(chemin)
