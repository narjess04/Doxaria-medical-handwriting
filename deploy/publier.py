r"""Mise en ligne sur Hugging Face : poids des modèles et API (Space Docker).

Prérequis : un compte Hugging Face, un jeton « Write » (https://huggingface.co/settings/tokens),
donné dans la variable HF_TOKEN (PowerShell : $env:HF_TOKEN = "hf_...").
Lancer depuis la racine du dépôt, avec le Python du backend (huggingface_hub y est installé) :

    backend\.venv\Scripts\python deploy/publier.py modeles --depot <compte>/meditrust-modeles
    backend\.venv\Scripts\python deploy/publier.py space   --depot <compte>/meditrust-api \
                                                           --modeles <compte>/meditrust-modeles

`space` envoie le code du backend, les référentiels (data/) et deploy/space/, puis
enregistre comme secrets du Space les clés de backend/.env et le jeton d'accès de l'API.
"""

import argparse
import os
import secrets
from pathlib import Path

from huggingface_hub import HfApi

RACINE = Path(__file__).resolve().parents[1]
# Clés de backend/.env recopiées en secrets du Space (jamais dans les fichiers envoyés).
SECRETS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "OCR_API_KEY", "OCR_BASE_URL", "OCR_MODEL")


def lire_env(chemin: Path) -> dict[str, str]:
    valeurs = {}
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                valeurs[cle.strip()] = valeur.strip()
    return valeurs


def publier_modeles(api: HfApi, depot: str, prive: bool) -> None:
    api.create_repo(depot, repo_type="model", private=prive, exist_ok=True)
    api.upload_folder(repo_id=depot, repo_type="model", folder_path=RACINE / "backend" / "models",
                      ignore_patterns=[".gitkeep", "**/.gitkeep"], commit_message="Poids des modèles MediTrust")
    print(f"Poids publiés : https://huggingface.co/{depot}")


def publier_space(api: HfApi, depot: str, modeles: str, jeton: str | None) -> None:
    api.create_repo(depot, repo_type="space", space_sdk="docker", exist_ok=True)
    api.upload_folder(
        repo_id=depot, repo_type="space", folder_path=RACINE, commit_message="Code de l'API MediTrust",
        allow_patterns=["backend/app/**", "backend/main.py", "backend/requirements.txt", "data/**"],
        ignore_patterns=["**/__pycache__/**", "**/*.pyc", "data/medicaments/raw/**"],
    )
    for fichier in ("Dockerfile", "README.md"):
        api.upload_file(repo_id=depot, repo_type="space", path_or_fileobj=RACINE / "deploy" / "space" / fichier,
                        path_in_repo=fichier, commit_message=f"{fichier} du Space")

    env = lire_env(RACINE / "backend" / ".env")
    for cle in SECRETS:
        if env.get(cle):
            api.add_space_secret(depot, cle, env[cle])
    api.add_space_variable(depot, "HF_MODELES", modeles)
    jeton = jeton or secrets.token_urlsafe(32)
    api.add_space_secret(depot, "API_TOKEN", jeton)

    proprietaire, nom = depot.split("/")
    print(f"Space publié : https://huggingface.co/spaces/{depot} (construction : quelques minutes)")
    print("À mettre dans les variables d'environnement du frontend (Vercel) :")
    print(f"  BACKEND_URL=https://{proprietaire.lower()}-{nom.lower()}.hf.space")
    print(f"  BACKEND_TOKEN={jeton}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = parser.add_subparsers(dest="cible", required=True)
    m = sous.add_parser("modeles", help="envoyer backend/models/ dans un dépôt de modèles")
    m.add_argument("--depot", required=True, help="ex. narjess04/meditrust-modeles")
    m.add_argument("--prive", action="store_true", help="dépôt privé (le Space aura alors besoin de HF_TOKEN)")
    s = sous.add_parser("space", help="envoyer l'API dans un Space Docker")
    s.add_argument("--depot", required=True, help="ex. narjess04/meditrust-api")
    s.add_argument("--modeles", required=True, help="dépôt des poids, ex. narjess04/meditrust-modeles")
    s.add_argument("--jeton", help="jeton d'accès de l'API à réutiliser (sinon, un nouveau est généré)")
    args = parser.parse_args()

    api = HfApi(token=os.environ.get("HF_TOKEN"))
    if args.cible == "modeles":
        publier_modeles(api, args.depot, args.prive)
    else:
        publier_space(api, args.depot, args.modeles, args.jeton)


if __name__ == "__main__":
    main()
