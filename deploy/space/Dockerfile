# API MediTrust (backend + référentiels) pour un Space Hugging Face « Docker ».
# Construit par Hugging Face à partir des fichiers envoyés par deploy/publier.py ;
# en local, depuis la racine du dépôt : docker build -f deploy/space/Dockerfile .

FROM python:3.12-slim

# libGL/glib : OpenCV (YOLOv8) ; Tesseract + français : texte du cachet et numéro de bulletin.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 tesseract-ocr tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face lance le conteneur avec l'utilisateur 1000.
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# PyTorch en version processeur (la version CUDA pèse plusieurs Go de plus).
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r backend/requirements.txt transformers pytesseract huggingface_hub

COPY --chown=user backend/ backend/
COPY --chown=user data/ data/

USER user
ENV PYTHONUNBUFFERED=1 HF_HOME=/home/user/.cache/huggingface
WORKDIR /home/user/app/backend
EXPOSE 7860

# Poids téléchargés depuis HF_MODELES à chaque démarrage (le disque du Space n'est pas conservé).
CMD python -m app.core.telechargement && uvicorn main:app --host 0.0.0.0 --port 7860
