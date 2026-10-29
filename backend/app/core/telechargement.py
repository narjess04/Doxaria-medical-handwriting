"""Télécharge les poids des modèles depuis Hugging Face dans backend/models/.

Lancé avant l'API sur le serveur (voir deploy/Dockerfile) :
    python -m app.core.telechargement

Sans config.HF_MODELES, ne fait rien (en local, les poids sont déjà dans models/).
Un dépôt privé demande la variable HF_TOKEN (jeton en lecture seule).
"""

from app.core import config


def telecharger() -> None:
    if not config.HF_MODELES:
        print("HF_MODELES non défini : poids locaux utilisés.")
        return
    from huggingface_hub import snapshot_download

    # Le serveur n'exécute que les .onnx (onnxruntime) : les .pt ne sont pas téléchargés.
    snapshot_download(config.HF_MODELES, local_dir=config.MODELS_DIR, allow_patterns=["*.onnx", "*/*.onnx"])
    print(f"Poids téléchargés depuis {config.HF_MODELES} dans {config.MODELS_DIR}.")


if __name__ == "__main__":
    telecharger()
