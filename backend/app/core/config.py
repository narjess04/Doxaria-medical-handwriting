"""Configuration : chemins des données, modèle de langage, CORS.

Les secrets (clé d'API) sont lus dans backend/.env, jamais versionné.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

# Référentiels officiels (médicaments DPM/CNAM, termes médicaux).
DATA_DIR = BACKEND_DIR.parent / "data"

# Poids des modèles (non versionnés). Chacun est chargé à sa première utilisation.
MODELS_DIR = BACKEND_DIR / "models"
MODELE_CLASSIFICATION = MODELS_DIR / "classification" / "cnn_ordonnance_bulletin.pt"  # CNN 2 classes
MODELE_FRAUDE = MODELS_DIR / "fraude" / "docteur_cachet.pt"          # YOLOv8 : docteur, stamp
MODELE_BULLETIN = MODELS_DIR / "bulletin" / "champs_bulletin.pt"     # YOLOv8 : 9 champs du bulletin
# Détecteur de lignes : celui du notebook 03 s'il existe, sinon celui de l'ancienne version.
MODELE_LIGNES = next((p for p in (MODELS_DIR / "yolo" / "doxaria-lignes.pt", MODELS_DIR / "yolo" / "lignes_texte.pt")
                      if p.exists()), MODELS_DIR / "yolo" / "doxaria-lignes.pt")
MODELE_DATE = MODELS_DIR / "ordonnance" / "date_texte.pt"            # YOLOv8 : date, text
MODELE_TROCR = MODELS_DIR / "trocr-doxaria"                           # TrOCR fine-tuné (notebook 02)
# En attendant le fine-tuning : TrOCR pré-entraîné sur l'écriture manuscrite (téléchargé une fois).
TROCR_SECOURS = os.environ.get("TROCR_SECOURS", "microsoft/trocr-base-handwritten")
TROCR_FAISCEAUX = 1  # lecture simple : sur processeur, 3 faisceaux coûtent +20 % de temps pour un gain faible

# Lecture des ordonnances par une API, dans cet ordre (sinon TrOCR, ci-dessus) :
# 1. modèle de vision compatible OpenAI (OpenRouter) : lit la page ET range médecin,
#    date, patient et prescription ; ~0,0003 $ par ordonnance avec Qwen3-VL 30B ;
# 2. Mistral OCR : texte seul, rangé ensuite par mots-clés ; version figée la moins chère.
OCR_API_KEY = os.environ.get("OCR_API_KEY", "")
OCR_BASE_URL = os.environ.get("OCR_BASE_URL", "https://openrouter.ai/api/v1")
OCR_MODEL = os.environ.get("OCR_MODEL", "qwen/qwen3-vl-30b-a3b-instruct")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_OCR_MODEL = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-2512")
OCR_TIMEOUT = 90

SEUIL_DETECTION = 0.3       # confiance minimale des boîtes YOLO
SEUIL_SIMILARITE_CACHET = 0.2  # part des mots du cachet retrouvés dans la zone « docteur »
TAILLE_MAX_IMAGE = 10 * 1024 * 1024

# Modèle de langage de l'assistant : toute API compatible OpenAI (Groq, OpenRouter…).
# Sans clé, l'assistant répond depuis les seuls référentiels.
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")
LLM_TIMEOUT = 45

# Déploiement (voir README) :
# - API_TOKEN : jeton partagé avec le frontend ; s'il est défini, toutes les routes sauf
#   /api/health l'exigent (en-tête « Authorization: Bearer … »). Vide en local.
# - HF_MODELES : dépôt Hugging Face des poids (ex. « narjess04/meditrust-modeles »),
#   téléchargés dans models/ au démarrage par `python -m app.core.telechargement`.
API_TOKEN = os.environ.get("API_TOKEN", "")
HF_MODELES = os.environ.get("HF_MODELES", "")

CORS_ORIGINS =os.environ.get("CORS_ORIGINS", "http://127.0.0.1:5000,http://localhost:5000").split(",")
