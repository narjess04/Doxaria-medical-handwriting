"""Type de document (ordonnance ou bulletin de soins) par le CNN de l'ancienne version."""

from functools import lru_cache

from PIL import Image

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
    import torch
    from torchvision.transforms.functional import to_tensor

    modele = modeles.cnn()
    x = to_tensor(image.convert("RGB").resize((TAILLE, TAILLE), Image.BILINEAR)).unsqueeze(0)
    with modeles.verrou("cnn"), torch.inference_mode():
        probas = torch.softmax(modele(x), dim=1)[0]
    i = int(probas.argmax())
    return CLASSES[i], round(float(probas[i]), 4)
