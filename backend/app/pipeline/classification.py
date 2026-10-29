"""Type de document (ordonnance ou bulletin de soins) par le CNN de l'ancienne version."""

from functools import lru_cache

import numpy as np
from PIL import Image

from app.core import config

from . import modeles

# Ordre des classes à l'entraînement : ['Bulletin', 'Ordonnaces'].
CLASSES = ["bulletin", "ordonnance"]
TAILLE = 128  # le CNN attend du 128x128


@lru_cache(maxsize=1)
def _architecture():
    """Classe du réseau, construite à la demande pour ne pas importer PyTorch au démarrage."""
    import torch.nn as nn
    import torch.nn.functional as F

    class OrdonnanceClassifierCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
            self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
            self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
            self.pool = nn.MaxPool2d(2, 2)
            self.dropout = nn.Dropout(0.3)
            self.fc1 = nn.Linear(128 * 16 * 16, 128)
            self.fc2 = nn.Linear(128, len(CLASSES))

        def forward(self, x):
            x = self.pool(F.relu(self.conv1(x)))  # 32 x 64 x 64
            x = self.pool(F.relu(self.conv2(x)))  # 64 x 32 x 32
            x = self.pool(F.relu(self.conv3(x)))  # 128 x 16 x 16
            x = self.dropout(x).flatten(1)
            return self.fc2(F.relu(self.fc1(x)))

    return OrdonnanceClassifierCNN


def OrdonnanceClassifierCNN():
    return _architecture()()


def classer(image: Image.Image) -> tuple[str, float]:
    """(type de document, probabilité)."""
    entree = image.convert("RGB").resize((TAILLE, TAILLE), Image.BILINEAR)
    if onnx := modeles.version_onnx(config.MODELE_CLASSIFICATION):
        # Même entrée que to_tensor : RGB entre 0 et 1, canaux en premier.
        x = (np.asarray(entree, dtype=np.float32) / 255).transpose(2, 0, 1)[None]
        session = modeles.session_onnx(onnx)
        with modeles.verrou("cnn"):
            logits = session.run(None, {session.get_inputs()[0].name: x})[0][0]
        probas = np.exp(logits - logits.max())
        probas /= probas.sum()
        i = int(probas.argmax())
        return CLASSES[i], round(float(probas[i]), 4)

    import torch
    from torchvision.transforms.functional import to_tensor

    modele = modeles.cnn()
    x = to_tensor(entree).unsqueeze(0)
    with modeles.verrou("cnn"), torch.inference_mode():
        probas = torch.softmax(modele(x), dim=1)[0]
    i = int(probas.argmax())
    return CLASSES[i], round(float(probas[i]), 4)
