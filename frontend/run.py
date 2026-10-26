"""Point d'entrée du frontend : python run.py"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # HOST=0.0.0.0 pour ouvrir le site depuis un téléphone du même réseau.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=True)
