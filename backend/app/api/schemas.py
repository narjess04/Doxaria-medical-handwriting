"""Schémas des requêtes et réponses."""

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class ChatRequete(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # Seuls les 8 derniers messages sont utilisés (voir routes.chat).
    historique: list[Message] = Field(default_factory=list, max_length=40)


class ChatReponse(BaseModel):
    """Réponse du modèle (`markdown`) ou réponse de repli (`titre`, `fiche`, `texte`)."""
    markdown: str | None = None
    titre: str | None = None
    fiche: list[tuple[str, str]] | None = None
    texte: str | None = None
    categorie: str | None = None
    suggestions: list[str] | None = None
    medicaments: list[str] = Field(default_factory=list)
    source: str | None = None


class TexteRequete(BaseModel):
    texte: str = Field(max_length=20000)


class Medicament(BaseModel):
    nom: str
    dci: str
    classe: str
    sous_classe: str
    laboratoire: str
    type: str
    veic: str
    rembourse: bool
    prix: float | None
    presentations: list[str]


class Verification(BaseModel):
    medicaments: list[Medicament]


class Boite(BaseModel):
    classe: str
    confiance: float
    bbox: list[float]
    libelle: str | None = None
    texte: str | None = None


class Classification(BaseModel):
    type: Literal["ordonnance", "bulletin"]
    confiance: float


class Extraction(BaseModel):
    type: Literal["ordonnance", "bulletin"]
    confiance_type: float | None = None  # renseigné si le type a été détecté automatiquement
    lecture: bool = True  # False : lignes détectées mais pas lues (TrOCR indisponible)
    medecin: str | None = None
    date: str | None = None  # jj/mm/aaaa
    patient: str | None = None  # lu seulement par le modèle de vision
    texte: str
    numero: str | None = None
    # Ordonnance : une boîte par ligne ; classe = medecin | date | prescription,
    # texte = lecture corrigée, libelle = lecture brute si la correction l'a modifiée.
    champs: list[Boite] = Field(default_factory=list)
    medicaments: list[str] = Field(default_factory=list)  # reconnus dans le référentiel
    modele: str | None = None  # modèle de lecture utilisé
    largeur: int  # taille de l'image analysée, pour placer les boîtes
    hauteur: int


class DetailsFraude(BaseModel):
    cachet: float | None
    entete_medecin: float | None
    correspondance: float | None
    ocr: bool
    boites: list[Boite]


class Fraude(BaseModel):
    verdict: Literal["conforme", "suspect"]
    message: str
    score: float
    details: DetailsFraude


class Statistiques(BaseModel):
    noms: int
    presentations: int
    termes: int
