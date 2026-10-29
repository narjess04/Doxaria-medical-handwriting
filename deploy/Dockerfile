# API MediTrust (backend + référentiels) pour Render, offre gratuite (512 Mo de RAM).
# Version légère : modèles au format ONNX (onnxruntime), sans PyTorch ni Ultralytics.
# En local, depuis la racine du dépôt : docker build -f deploy/Dockerfile .

FROM python:3.12-slim

# Tesseract + français : texte du cachet (fraude) et numéro de bulletin.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY backend/main.py backend/main.py
COPY data data

ENV PYTHONUNBUFFERED=1
WORKDIR /app/backend

# Poids .onnx téléchargés depuis HF_MODELES à chaque démarrage (le disque n'est pas conservé).
# Render fournit le port dans PORT.
CMD python -m app.core.telechargement && uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
