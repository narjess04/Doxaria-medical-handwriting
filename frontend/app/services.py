"""Appels à l'API du backend (backend/).

Le frontend ne contient aucune logique métier : OCR, détection de fraude,
référentiels des médicaments et assistant (RAG) sont dans le backend.
Quand le backend ne répond pas, chaque fonction renvoie un repli explicite.
"""

import requests
from flask import current_app

# Résultats d'exemple tant que le pipeline OCR n'est pas branché.
DEMO_DOCUMENT = {
    "ordonnance": {
        "medecin": "Dr Sami Trabelsi — Médecine générale",
        "texte": "Tunis, le 12/03/2026\nM. Ahmed Gharbi\nAugmentin 1g/125mg\n"
                 "1 sachet x 3/j pendant 7 jours\nDoliprane 1000 mg\n1 cp si douleur",
        "numero": None,
    },
    "bulletin": {
        "medecin": "Dr Leila Ben Salah — Pédiatrie",
        "texte": "Bulletin de soins CNAM\nConsultation pédiatrique\nHonoraires : 50,000 DT",
        "numero": "0711-9459343",
    },
}

DEMO_FRAUDE = {
    "verdict": "conforme",
    "message": "Aucune anomalie détectée sur le cachet, la signature et les montants.",
    "score": 0.12,
}

INDISPONIBLE = ("L'assistant est indisponible : le backend ne répond pas. "
                "Lancez-le avec `uvicorn main:app --port 8000` dans le dossier backend.")


def _url(chemin):
    return current_app.config["BACKEND_URL"].rstrip("/") + chemin


def _get(chemin, timeout=5):
    r = requests.get(_url(chemin), timeout=timeout)
    r.raise_for_status()
    return r.json()


def _post(chemin, timeout=60, **kwargs):
    r = requests.post(_url(chemin), timeout=timeout, **kwargs)
    r.raise_for_status()
    return r.json()


def _post_image(chemin, image_path, timeout=60, **data):
    with open(image_path, "rb") as f:
        return _post(chemin, timeout=timeout, files={"image": f}, data=data)


def etat_backend():
    """{"status": "ok", "llm": bool}, ou None si le backend ne répond pas."""
    try:
        return _get("/api/health", timeout=3)
    except (requests.RequestException, ValueError):
        return None


def _zones(res):
    """Boîtes du backend (pixels) -> fractions de l'image, pour les dessiner quelle que soit sa taille."""
    w, h = res.get("largeur") or 1, res.get("hauteur") or 1
    return [{"classe": b.get("classe", ""), "libelle": b.get("texte") or b.get("libelle") or b.get("classe", ""),
             "x": b["bbox"][0] / w, "y": b["bbox"][1] / h,
             "l": (b["bbox"][2] - b["bbox"][0]) / w, "h": (b["bbox"][3] - b["bbox"][1]) / h}
            for b in res.get("champs", []) if len(b.get("bbox", [])) == 4]


def analyser_document(image_path, type_document):
    """{medecin, texte, numero, type, demo, zones} pour une ordonnance ou un bulletin.

    `type_document` : "auto" (le CNN du backend décide), "ordonnance" ou "bulletin".
    `demo` : le texte est un exemple (lecture pas encore disponible) ; les zones,
    elles, sont toujours celles réellement détectées.
    """
    try:
        # TrOCR sur processeur : environ 4 s par ligne, d'où un délai large.
        res = _post_image("/api/extract", image_path, timeout=180, type=type_document)
        type_document = res.get("type", type_document)
        if not res.get("lecture", True):
            # Lignes détectées mais pas lues : texte d'exemple, zones réelles.
            return {**DEMO_DOCUMENT[type_document], "type": type_document, "demo": True, "zones": _zones(res)}
        return {"medecin": res.get("medecin"), "texte": res.get("texte", ""), "numero": res.get("numero"),
                "date": res.get("date"), "modele": res.get("modele"),
                "type": type_document, "demo": False, "zones": _zones(res)}
    except requests.HTTPError as e:
        # 501 : modèle pas encore disponible ; le backend indique quand même le type détecté.
        try:
            detail = e.response.json().get("detail")
            type_document = detail.get("type", type_document) if isinstance(detail, dict) else type_document
        except ValueError:
            pass
    except (requests.RequestException, ValueError):
        pass
    type_document = type_document if type_document in DEMO_DOCUMENT else "ordonnance"
    return {**DEMO_DOCUMENT[type_document], "type": type_document, "demo": True, "zones": []}


def analyser_fraude(image_path):
    """{verdict: conforme|suspect, message, score, demo}."""
    try:
        return {**_post_image("/api/fraud", image_path), "demo": False}
    except (requests.RequestException, ValueError):
        return {**DEMO_FRAUDE, "demo": True}


def verifier_medicaments(texte):
    """Fiches des médicaments du référentiel cités dans le texte ; None si indisponible."""
    try:
        return _post("/api/medicaments/verifier", json={"texte": texte}, timeout=10)["medicaments"]
    except (requests.RequestException, ValueError, KeyError):
        return None


def statistiques_referentiels():
    try:
        return _get("/api/referentiels/stats")
    except (requests.RequestException, ValueError):
        return None


def discuter(question, historique):
    """Réponse de l'assistant (RAG du backend)."""
    try:
        return _post("/api/chat", json={"question": question, "historique": historique})
    except (requests.RequestException, ValueError):
        return {"texte": INDISPONIBLE}
