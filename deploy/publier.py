r"""Publie les poids des modèles (backend/models/) dans un dépôt de modèles Hugging Face.

Le serveur (Render) les télécharge au démarrage : voir app/core/telechargement.py.
Prérequis : un compte Hugging Face et un jeton « Write » (https://huggingface.co/settings/tokens),
donné dans la variable HF_TOKEN (PowerShell : $env:HF_TOKEN = "hf_...").
Lancer depuis la racine du dépôt, après scripts/exporter_onnx.py :

    backend\.venv\Scripts\python deploy/publier.py --depot <compte>/meditrust-modeles
"""

import argparse
import os
from pathlib import Path

from huggingface_hub import HfApi

RACINE = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--depot", required=True, help="ex. narjess05/meditrust-modeles")
    parser.add_argument("--prive", action="store_true", help="dépôt privé (le serveur aura alors besoin de HF_TOKEN)")
    args = parser.parse_args()

    api = HfApi(token=os.environ.get("HF_TOKEN"))
    api.create_repo(args.depot, repo_type="model", private=args.prive, exist_ok=True)
    api.upload_folder(repo_id=args.depot, repo_type="model", folder_path=RACINE / "backend" / "models",
                      ignore_patterns=[".gitkeep", "**/.gitkeep"], commit_message="Poids des modèles MediTrust")
    print(f"Poids publiés : https://huggingface.co/{args.depot}")


if __name__ == "__main__":
    main()
