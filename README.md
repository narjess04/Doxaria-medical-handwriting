# MediTrust · Doxaria

**Numérisation des documents médicaux manuscrits tunisiens.**
Une photo d'ordonnance ou de bulletin de soins devient un texte structuré et
vérifié : médecin, date, médicaments contrôlés dans les référentiels officiels
(DPM, CNAM), détection de fraude, et un assistant médical pour comprendre un
traitement.

- **Site web** (Flask) utilisable sur ordinateur et téléphone : import depuis le PC, la galerie ou l'appareil photo.
- **API** (FastAPI) qui regroupe la vision, l'OCR, les référentiels et l'assistant.
- **Modèles** : CNN, YOLOv8, TrOCR, plus un modèle de langage pour l'assistant.

## Fonctionnalités

| Fonction | Ce qu'elle fait |
|---|---|
| **Type de document** | Un CNN distingue ordonnance et bulletin de soins (détection automatique). |
| **Lecture d'ordonnance** | YOLOv8 repère les lignes, TrOCR les lit. Le médecin (zone « docteur ») et la date (zone « date ») sont isolés, et chaque ligne est corrigée avec le référentiel des médicaments et des termes médicaux. |
| **Bulletin de soins** | YOLOv8 repère les 9 champs (n° de bulletin, CIN, adhérent, patient, signature…) et signale ceux qui manquent. |
| **Vérification des médicaments** | Chaque médicament cité est retrouvé dans la liste des AMM (DPM) et des remboursements (CNAM) : DCI, classe, remboursement, prix. |
| **Détection de fraude** | YOLOv8 repère le cachet et l'en-tête du médecin, puis on vérifie que le cachet porte bien le nom du médecin. |
| **Assistant médical** | RAG : les fiches officielles des médicaments cités sont transmises à un modèle de langage, qui répond sur les effets indésirables, les interactions, la grossesse… et propose des hypothèses pour une ordonnance (jamais un diagnostic). |
| **Espace personnel** | Comptes, historique, correction manuelle du texte, suppression des documents. |

## Architecture

```
 Navigateur (PC / téléphone)
        │
        ▼
 frontend/  Flask — pages, comptes, historique (SQLite)
        │  HTTP (JSON)
        ▼
 backend/   FastAPI
   ├─ /api/classify            CNN ordonnance / bulletin
   ├─ /api/extract             YOLOv8 (lignes, médecin, date) → TrOCR → correction par le référentiel
   ├─ /api/fraud               YOLOv8 cachet + en-tête → comparaison des noms
   ├─ /api/medicaments/verifier
   └─ /api/chat                RAG : référentiels data/ + modèle de langage (Groq)
        │
        ▼
 data/  référentiels officiels (CSV) · backend/models/  poids des modèles
```

## Modèles

| Modèle | Rôle | Fichier (`backend/models/`) | Résultat à l'entraînement |
|---|---|---|---|
| CNN (3 convolutions) | ordonnance ou bulletin | `classification/cnn_ordonnance_bulletin.pt` 
| YOLOv8n | lignes de texte | `yolo/lignes_texte.pt` | mAP50 0,929 |
| YOLOv8n | date de l'ordonnance | `ordonnance/date_texte.pt` | mAP50 0,804 |
| YOLOv8n | cachet + en-tête du médecin | `fraude/docteur_cachet.pt` | mAP50 0,886 |
| YOLOv8n | 9 champs du bulletin | `bulletin/champs_bulletin.pt` | mAP50 0,995 |
| TrOCR fine-tuné | lecture de l'écriture manuscrite 

**TrOCR fine-tuné sur des ordonnances tunisiennes.** Le modèle de lecture est
TrOCR (`microsoft/trocr-base-handwritten`), fine-tuné sur notre propre jeu de
données : **plus de 210 ordonnances médicales tunisiennes** manuscrites,
découpées **ligne par ligne** puis **annotées à la main** (transcription exacte
de chaque ligne : médicaments, dosages, posologies, en-têtes et dates). Le
modèle apprend ainsi l'écriture des médecins, le français médical et les noms
de médicaments vendus en Tunisie. Chaque ligne lue est ensuite corrigée avec
le référentiel officiel des médicaments et des termes médicaux. Le
fine-tuning et la comparaison avec EasyOCR et Tesseract sont dans les
[notebooks Colab](notebooks/README.md).

Tant que les poids fine-tunés ne sont pas dans `backend/models/trocr-doxaria/`,
le backend utilise TrOCR pré-entraîné (environ 1,3 Go, téléchargé une seule fois).

## Données

- [`data/medicaments/`](data/medicaments/README.md) : 6 053 présentations
  autorisées (liste des AMM de la DPM) et 3 283 médicaments remboursés (CNAM),
  avec leurs sources, leurs empreintes SHA-256 et le script de reconstruction.
- [`data/termes_medicaux/`](data/termes_medicaux/README.md) : 262 termes et
  abréviations médicales (ATCD, NFS, HTA, x3/j…).

## Structure

```
Doxaria/
├── backend/                   API FastAPI
│   ├── main.py                point d'entrée (uvicorn)
│   ├── .env                   clé du modèle de langage (non versionné)
│   ├── app/
│   │   ├── api/               routes et schémas
│   │   ├── core/config.py     chemins des modèles, seuils, modèle de langage
│   │   ├── chatbot/           RAG : référentiels, génération, réponses de repli
│   │   └── pipeline/          prétraitement, CNN, YOLOv8, TrOCR, correction, fraude, bulletin
│   ├── models/                poids .pt et .onnx (non versionnés, publiés sur Hugging Face)
│   └── tests/
├── frontend/                  site MediTrust (Flask)
│   ├── app/                   comptes, outils, appels au backend, templates, CSS/JS
│   ├── api/index.py           point d'entrée Vercel
│   ├── vercel.json
│   └── tests/
├── deploy/                    mise en ligne : Dockerfile de l'API (Render), publication des poids
├── render.yaml                configuration Render de l'API
├── data/                      référentiels officiels
├── notebooks/                 Colab : datasets, fine-tuning TrOCR, YOLOv8, comparaison des OCR
└── scripts/                   construction des référentiels
```

## Installation

Prérequis : Python 3.11 ou plus. Les modèles tournent sur processeur, sans
carte graphique.

```bash
# 1. Backend — http://127.0.0.1:8000/docs (documentation interactive de l'API)
cd backend
python -m venv .venv
.venv\Scripts\activate             # Windows ; macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt   # léger : modèles au format ONNX
uvicorn main:app --port 8000

# 2. Frontend — http://127.0.0.1:5000 (dans un second terminal)
cd frontend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Les poids des modèles ne sont pas dans le dépôt : ils sont publiés sur
[Hugging Face](https://huggingface.co/narjess05/meditrust-modeles), à placer dans
`backend/models/`. `GET /api/health` indique ceux qui sont présents.

**Deux formats de modèles.** Le backend exécute les modèles au format **ONNX**
avec `onnxruntime` (~50 Mo) dès que le `.onnx` existe, sinon le `.pt` avec
PyTorch. Pour entraîner, utiliser les `.pt` ou les convertir :

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-entrainement.txt          # PyTorch, Ultralytics, TrOCR, onnx
python ../scripts/exporter_onnx.py                    # .pt -> .onnx, à côté des originaux
```

### Configuration

`backend/.env` (jamais versionné), à créer à partir de
[`backend/.env.example`](backend/.env.example) :

```ini
LLM_API_KEY=...                                # clé Groq
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b
```

Sans clé, l'assistant répond à partir des seuls référentiels. Facultatif :
[Tesseract](https://github.com/UB-Mannheim/tesseract/wiki), avec la langue
française et `pip install pytesseract`, pour lire le texte du cachet (fraude) et
le numéro de bulletin.

Pour ouvrir le site depuis un téléphone du même réseau (Wi-Fi) :

```powershell
$env:HOST = "0.0.0.0"; python run.py     # macOS/Linux : HOST=0.0.0.0 python run.py
ipconfig                                  # adresse IPv4 du PC, ex. 192.168.1.20
```

puis, sur le téléphone, `http://<ip-du-pc>:5000`. Windows demande la première
fois d'autoriser Python dans le pare-feu (réseau privé). Seul le frontend est
exposé : il appelle le backend sur le PC.

Le bouton « Prendre une photo » ouvre l'appareil photo du téléphone, même en
HTTP. La photo est remise à l'endroit, réduite (2400 px au plus) et convertie
en JPEG dans le navigateur avant l'envoi : les photos lourdes ou en HEIC
(iPhone) passent. Sur ordinateur, le bouton « Webcam » affiche un aperçu en
direct ; il n'apparaît qu'en HTTPS ou sur `localhost`, comme l'exige le
navigateur pour accéder à la caméra.

## Déploiement

Le site est déployé en trois parties, toutes sur des offres gratuites :

```
 Navigateur ──► frontend Flask ─────────────── Vercel
                    │  HTTPS + jeton d'accès
                    ▼
                API (backend, modèles ONNX) ── Render (Docker)
                    ▲
                poids des modèles ──────────── dépôt de modèles Hugging Face
```

L'API en ligne n'utilise pas PyTorch : le CNN et les YOLOv8 sont exécutés au
format ONNX, ce qui tient dans les 512 Mo de mémoire de l'offre gratuite de Render.

### 1. Hugging Face : poids des modèles

1. Créer un compte sur [huggingface.co](https://huggingface.co), puis un jeton
   d'accès de type **Write** dans *Settings → Access Tokens*.
2. Convertir les modèles en ONNX (voir *Installation*), puis, depuis la racine
   du dépôt (PowerShell) :

   ```powershell
   $env:HF_TOKEN = "hf_..."
   backend\.venv\Scripts\python deploy/publier.py --depot <compte>/meditrust-modeles
   ```

   Le contenu de `backend/models/` (`.pt` et `.onnx`) est envoyé dans un dépôt
   de modèles public. L'API ne télécharge que les `.onnx` à son démarrage.

### 2. Render : API

1. Créer un compte sur [render.com](https://render.com) avec GitHub.
2. *New → Blueprint*, choisir ce dépôt : Render lit [`render.yaml`](render.yaml)
   et construit [`deploy/Dockerfile`](deploy/Dockerfile).
3. Render demande la valeur des clés marquées `sync: false` : recopier celles de
   `backend/.env`. Le jeton d'accès `API_TOKEN` est généré automatiquement.
4. Une fois le service *Live* : `https://meditrust-api.onrender.com/api/health`
   (l'adresse exacte est affichée par Render). Noter cette adresse et la valeur
   de `API_TOKEN` (*Environment* du service).

L'offre gratuite se met en veille après 15 minutes sans visite : la première
analyse suivante attend alors environ une minute.

### 3. Base de données

Créer une base PostgreSQL gratuite sur [neon.tech](https://neon.tech) (région
Europe) et copier son adresse de connexion (`postgresql://…`). Les comptes,
l'historique et les images y sont conservés : le disque de Vercel ne l'est pas.

### 4. Vercel : site web

1. Sur [vercel.com](https://vercel.com), *Add New → Project*, importer ce dépôt
   GitHub et choisir **`frontend`** comme *Root Directory*.
2. Variables d'environnement :

   | Variable | Valeur |
   |---|---|
   | `BACKEND_URL` | adresse de l'API sur Render |
   | `BACKEND_TOKEN` | valeur de `API_TOKEN` sur Render |
   | `DATABASE_URL` | adresse PostgreSQL de Neon |
   | `SECRET_KEY` | longue chaîne aléatoire (sessions) |
   | `HTTPS` | `1` (cookies sécurisés) |

3. *Deploy*. Le site est public : tout le monde peut l'utiliser, et le bouton
   **« Essayer la démo sans compte »** permet de tester sans rien enregistrer.

## Tests

```bash
cd backend  && python -m pytest tests    # API, pipeline, RAG (modèles simulés + un test avec les vrais poids)
cd frontend && python -m pytest tests    # comptes, documents, droits d'accès, backend arrêté
```

## Limites

- Les résultats de lecture doivent être **relus par un professionnel de santé** ;
  l'assistant ne pose pas de diagnostic.
- TrOCR est entraîné sur un peu plus de 210 ordonnances : une écriture très
  différente de celles du jeu de données peut être moins bien lue.
- Le référentiel DPM est un instantané de janvier 2024 (voir `data/medicaments/README.md`).
- La base SQLite convient à une démonstration ; pour un usage réel, PostgreSQL
  (variable `DATABASE_URL`) et un hébergement adapté aux données de santé.

---

Projet académique réalisé à **ESPRIT** (École Supérieure Privée d'Ingénierie et
de Technologies, Tunisie) en collaboration avec la startup **Doxaria**, en 2025.
