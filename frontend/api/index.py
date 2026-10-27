"""Point d'entrée Vercel : l'application Flask, servie comme une fonction Python."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # dossier frontend/ (app, config)

from app import create_app  # noqa: E402

app = create_app()
