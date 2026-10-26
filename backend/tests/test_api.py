"""Tests de l'API. Le modèle de langage est simulé : aucun appel réseau."""

import io

import pytest
import requests
from fastapi.testclient import TestClient
from PIL import Image

from app.chatbot import rag
from app.core import config
from app.pipeline import classification, correction, detection, ocr, recognition
from app.pipeline.modeles import ModeleIndisponible
from app.pipeline.preprocessing import charger_image
from main import app

client = TestClient(app)


@pytest.fixture
def sans_llm(monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "")


@pytest.fixture
def llm_simule(monkeypatch):
    """Remplace l'appel au modèle et garde ce qu'il a reçu."""
    appels = []
    monkeypatch.setattr(config, "LLM_API_KEY", "cle-de-test")

    def generer(question, historique, extraits):
        appels.append({"question": question, "historique": historique, "extraits": extraits})
        return "**Réponse simulée**"

    monkeypatch.setattr(rag, "generer", generer)
    return appels


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_stats_referentiels():
    s = client.get("/api/referentiels/stats").json()
    assert s["noms"] > 3000 and s["presentations"] > 6000 and s["termes"] > 250


def test_verifier_medicaments():
    r = client.post("/api/medicaments/verifier", json={"texte": "Augmentin 1g\n1 sachet x 3/j\nDoliprane 1000\nAugmentin"})
    noms = [m["nom"] for m in r.json()["medicaments"]]
    assert noms == ["AUGMENTIN", "DOLIPRANE"]
    augmentin = r.json()["medicaments"][0]
    assert "AMOXICILLINE" in augmentin["dci"] and augmentin["rembourse"]


def test_rag_donne_le_referentiel_au_modele(llm_simule):
    r = client.post("/api/chat", json={"question": "Effets secondaires de l'Augmentin ?"}).json()
    assert r["markdown"] == "**Réponse simulée**" and r["medicaments"] == ["AUGMENTIN"]
    assert "AUGMENTIN" in llm_simule[0]["extraits"] and "AMOXICILLINE" in llm_simule[0]["extraits"]


def test_rag_suit_la_conversation(llm_simule):
    historique = [{"role": "user", "content": "Parle-moi du Doliprane"},
                  {"role": "assistant", "content": "Le Doliprane est du paracétamol."}]
    r = client.post("/api/chat", json={"question": "Et pendant la grossesse ?", "historique": historique}).json()
    assert "DOLIPRANE" in r["medicaments"]
    assert llm_simule[0]["historique"] == historique


def test_rag_dci_et_termes(llm_simule):
    client.post("/api/chat", json={"question": "Interactions de l'ibuprofène ? Et c'est quoi la NFS ?"})
    extraits = llm_simule[0]["extraits"]
    assert "IBUPROFEN" in extraits and "numération formule sanguine" in extraits


def test_repli_si_le_modele_echoue(monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "cle-de-test")

    def panne(*_):
        raise requests.ConnectionError("hors ligne")

    monkeypatch.setattr(rag, "generer", panne)
    r = client.post("/api/chat", json={"question": "Augmentin"}).json()
    assert r["titre"] == "AUGMENTIN" and "markdown" not in r


@pytest.mark.parametrize("question, attendu", [
    ("Augmentin", "AMOXICILLINE"),
    ("C'est quoi la NFS ?", "numération formule sanguine"),
    ("augmantin", "AUGMENTIN"),
    ("amoxicilline", "AMOXAL"),
    ("ta tension", "Je n'ai trouvé"),
])
def test_repli_sans_cle(sans_llm, question, attendu):
    r = client.post("/api/chat", json={"question": question}).json()
    assert attendu.lower() in str(r).lower()


def test_validation_des_entrees():
    assert client.post("/api/chat", json={"question": ""}).status_code == 422
    assert client.post("/api/chat", json={"question": "x", "historique": [{"role": "system", "content": "x"}]}).status_code == 422


# ---------- Vision : les modèles sont simulés, sauf dans test_vrais_modeles ----------

def png(w=200, h=280):
    b = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(b, "PNG")
    return ("doc.png", b.getvalue(), "image/png")


def boite(classe, confiance=0.9, bbox=(10, 10, 100, 40)):
    return {"classe": classe, "confiance": confiance, "bbox": list(bbox)}


@pytest.fixture
def detections(monkeypatch):
    """detections.retour[chemin_du_modèle] = boîtes renvoyées par le faux YOLO."""
    class Faux:
        retour = {}

    monkeypatch.setattr(detection, "detecter", lambda chemin, image, seuil=0.3: Faux.retour.get(chemin, []))
    monkeypatch.setattr(ocr, "disponible", lambda: False)
    return Faux


def test_image_invalide():
    r = client.post("/api/fraud", files={"image": ("x.png", b"pas une image", "image/png")})
    assert r.status_code == 422 and "image" in r.json()["detail"]


def test_classify(monkeypatch):
    monkeypatch.setattr(classification, "classer", lambda image: ("bulletin", 0.98))
    assert client.post("/api/classify", files={"image": png()}).json() == {"type": "bulletin", "confiance": 0.98}


def test_fraude_sans_cachet(detections):
    detections.retour[config.MODELE_FRAUDE] = [boite("docteur")]
    r = client.post("/api/fraud", files={"image": png()}).json()
    assert r["verdict"] == "suspect" and "cachet" in r["message"]


def test_fraude_cachet_sans_ocr(detections):
    detections.retour[config.MODELE_FRAUDE] = [boite("docteur", 0.8), boite("stamp", 0.95, (50, 150, 150, 250))]
    r = client.post("/api/fraud", files={"image": png()}).json()
    assert r["verdict"] == "conforme" and not r["details"]["ocr"] and r["details"]["cachet"] == 0.95


def test_fraude_compare_les_noms(detections, monkeypatch):
    detections.retour[config.MODELE_FRAUDE] = [boite("docteur"), boite("stamp", bbox=(50, 150, 150, 250))]
    textes = iter(["Docteur Najoua MILADI Neurologie", "Dr N. MlLADI Najoua"])  # « l » lu au lieu de « I »
    monkeypatch.setattr(ocr, "lire", lambda image: next(textes))
    r = client.post("/api/fraud", files={"image": png()}).json()
    assert r["verdict"] == "conforme" and r["details"]["correspondance"] >= 0.5

    detections.retour[config.MODELE_FRAUDE] = [boite("docteur"), boite("stamp", bbox=(50, 150, 150, 250))]
    textes = iter(["Docteur Najoua MILADI Neurologie", "Dr Karim BEN SALAH Cardiologie"])
    assert client.post("/api/fraud", files={"image": png()}).json()["verdict"] == "suspect"


def test_extract_bulletin(detections, monkeypatch):
    detections.retour[config.MODELE_BULLETIN] = [boite("num_bulletin"), boite("cin"), boite("signa"),
                                                 boite("cin", 0.5)]
    monkeypatch.setattr(ocr, "lire_chiffres", lambda image: "0711945934")
    monkeypatch.setattr(classification, "classer", lambda image: ("bulletin", 0.97))
    r = client.post("/api/extract", files={"image": png()}, data={"type": "auto"}).json()
    assert r["type"] == "bulletin" and r["confiance_type"] == 0.97 and r["numero"] == "0711945934"
    assert [c["classe"] for c in r["champs"]] == ["num_bulletin", "cin", "signa"]  # un seul « cin »
    assert "Signature" in r["texte"] and "Tableau des actes" in r["texte"]  # présents / absents


def test_extract_ordonnance_sans_trocr(detections, monkeypatch):
    # Lignes détectées pour de vrai, mais TrOCR ne peut pas être chargé : pas de lecture.
    detections.retour[config.MODELE_LIGNES] = [boite("text")]

    def indisponible(images):
        raise ModeleIndisponible("transformers absent")

    monkeypatch.setattr(recognition, "lire_lignes", indisponible)
    monkeypatch.setattr(classification, "classer", lambda image: ("ordonnance", 0.9))
    r = client.post("/api/extract", files={"image": png()}, data={"type": "auto"}).json()
    assert r["type"] == "ordonnance" and r["lecture"] is False and len(r["champs"]) == 1
    assert (r["largeur"], r["hauteur"]) == (200, 280)


def test_extract_modele_absent(monkeypatch):
    def absent(image):
        raise ModeleIndisponible("CNN absent")

    monkeypatch.setattr(classification, "classer", absent)
    r = client.post("/api/extract", files={"image": png()}, data={"type": "auto"})
    assert r.status_code == 501 and r.json()["detail"]["type"] == "ordonnance"


def test_extract_ordonnance_complete(detections, monkeypatch):
    # Page 400 x 600 : en-tête du médecin en haut à gauche, date en haut à droite, puis la prescription.
    detections.retour[config.MODELE_LIGNES] = [
        boite("text", bbox=(20, 100, 380, 130)), boite("text", bbox=(20, 20, 180, 50)),
        boite("text", bbox=(300, 20, 390, 50)), boite("text", bbox=(40, 140, 380, 170)),
    ]
    detections.retour[config.MODELE_FRAUDE] = [boite("docteur", bbox=(10, 10, 200, 60))]
    detections.retour[config.MODELE_DATE] = [boite("date", bbox=(290, 10, 398, 60))]
    # Lectures dans l'ordre de lecture des lignes : en-tête, date, puis prescription.
    lectures = ["Dr Sami Trabelsi", "le 12-3-26", "Augmantin 1g", "1 sachet x 3/j"]
    monkeypatch.setattr(recognition, "lire_lignes", lambda images: lectures[:len(images)])
    r = client.post("/api/extract", files={"image": png(400, 600)}, data={"type": "ordonnance"}).json()
    assert r["medecin"] == "Dr Sami Trabelsi" and r["date"] == "12/03/2026"
    assert r["texte"] == "Augmentin 1g\n1 sachet x 3/j"  # nom du médicament corrigé
    assert r["medicaments"] == ["AUGMENTIN"]
    assert [c["classe"] for c in r["champs"]] == ["medecin", "date", "prescription", "prescription"]
    assert r["champs"][2]["libelle"] == "Augmantin 1g"  # lecture brute conservée


@pytest.mark.parametrize("lu, attendu", [
    ("Augmantin 1g", "Augmentin 1g"),
    ("DOLIPRAN 1000 mg", "DOLIPRANE 1000 mg"),
    ("amoxiciline 500", "amoxicilline 500"),
    ("1 sachet x 3/j pendant 7 jours", "1 sachet x 3/j pendant 7 jours"),  # posologie intacte
    ("Bilan : glycemie, NFS", "Bilan : glycémie, NFS"),
    ("Doliprane, 1 cp", "Doliprane, 1 cp"),  # déjà juste : rien ne change
    ("ricmissists will be still .", "ricmissists will be still ."),  # « still » n'est pas le médicament TILL
])
def test_correction_par_le_referentiel(lu, attendu):
    assert correction.corriger(lu)[0] == attendu


@pytest.mark.parametrize("lu, attendu", [
    ("le 12-3-26", "12/03/2026"), ("Tunis, le 05/11/2025", "05/11/2025"), ("12.03.2026", "12/03/2026"),
    ("45/13/2026", None), ("Augmentin", None),
])
def test_normaliser_date(lu, attendu):
    assert correction.normaliser_date(lu) == attendu


def test_regroupement_des_lignes():
    morceaux = [
        boite("text", 0.4, (16, 56, 64, 88)), boite("text", 0.37, (58, 61, 229, 88)),  # « Dr Sami Trabelsi »
        boite("text", 0.6, (473, 65, 573, 97)), boite("text", 0.33, (482, 66, 545, 96)),  # date, + un doublon
        boite("text", 0.78, (317, 208, 408, 242)), boite("text", 0.79, (410, 209, 501, 248)),  # ligne suivante
    ]
    resultat = [b["bbox"] for b in detection.regrouper_en_lignes(detection.dedoublonner(morceaux))]
    assert resultat == [[16, 56, 229, 88], [473, 65, 573, 97], [317, 208, 501, 248]]


def test_photo_remise_a_l_endroit():
    b = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation : tournée de 90°
    Image.new("RGB", (300, 100)).save(b, "JPEG", exif=exif)
    assert charger_image(b.getvalue()).size == (100, 300)


@pytest.mark.skipif(not config.MODELE_CLASSIFICATION.exists(), reason="poids absents")
def test_vrais_modeles():
    """Les vrais poids se chargent et répondent dans le bon format."""
    r = client.post("/api/classify", files={"image": png(400, 560)}).json()
    assert r["type"] in ("ordonnance", "bulletin") and 0.5 <= r["confiance"] <= 1
    assert client.post("/api/fraud", files={"image": png(400, 560)}).json()["verdict"] in ("conforme", "suspect")
