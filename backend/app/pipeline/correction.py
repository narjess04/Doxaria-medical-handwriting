"""Correction des lignes lues par l'OCR à l'aide des référentiels officiels.

Chaque groupe de 1 à 3 mots est comparé aux noms commerciaux (DPM/CNAM), aux
DCI et aux termes médicaux ; s'il est assez proche, il est remplacé par la forme
officielle (« Augmantin » -> « Augmentin »). Les nombres, dosages et mots
courants de posologie ne sont jamais modifiés.
"""

import re
from functools import lru_cache

from rapidfuzz import fuzz, process

from app.chatbot.referentiels import _index_dci, cle, medicaments, termes

SEUIL = 85  # similarité minimale (0-100) pour corriger
SEUIL_MOT_COURT = 92  # mots de moins de 7 lettres

# Mots fréquents sur une ordonnance, qui ne sont pas des médicaments.
MOTS_COURANTS = {
    "MATIN", "SOIR", "MIDI", "JOUR", "JOURS", "FOIS", "PENDANT", "AVANT", "APRES", "REPAS", "COUCHER",
    "TOUTES", "HEURES", "BESOIN", "DOULEUR", "FIEVRE", "BOITE", "BOITES", "SACHET", "SACHETS", "GELULE",
    "GELULES", "COMPRIME", "COMPRIMES", "CUILLERE", "MESURE", "APPLICATION", "RENOUVELER", "MOIS", "FAIRE",
    "BILAN", "PATIENT", "POIDS", "CONTROLE", "REPOS", "URGENCE", "TRAITEMENT", "DOCTEUR", "ORDONNANCE",
    "SEMAINE", "SEMAINES", "AGE", "ANS", "MADAME", "MONSIEUR", "ENFANT", "TUNIS", "SIROP", "GOUTTES",
}


@lru_cache(maxsize=1)
def _lexique():
    """(clés normalisées, formes officielles, catégories), noms les plus longs d'abord."""
    entrees = {}
    for k, fiche in medicaments().items():
        entrees.setdefault(k, (fiche["nom"], "medicament"))
    for k in _index_dci():
        entrees.setdefault(k, (k, "dci"))
    for k, t in termes().items():
        if len(k) >= 4:  # les abréviations courtes (TA, IM…) se corrigent mal par similarité
            entrees.setdefault(k, (t["terme"], "terme"))
    cles = sorted(entrees, key=len, reverse=True)
    return cles, [entrees[k] for k in cles]


def _casse(officiel: str, original: str) -> str:
    """Reprend la casse de l'écriture d'origine (MAJUSCULES, Titre ou minuscules)."""
    if original.isupper():
        return officiel.upper()
    if original[:1].isupper():
        return officiel[:1].upper() + officiel[1:].lower()
    return officiel.lower()


def corriger(ligne: str) -> tuple[str, list[dict]]:
    """(ligne corrigée, [{avant, apres, categorie, score}])."""
    cles, valeurs = _lexique()
    mots = ligne.split()
    sortie, corrections, i = [], [], 0
    while i < len(mots):
        for n in (3, 2, 1):
            if i + n > len(mots):
                continue
            bloc = " ".join(mots[i:i + n])
            # La ponctuation collée (« Augmantin, ») est conservée telle quelle.
            debut, coeur, fin = re.match(r"^(\W*)(.*?)(\W*)$", bloc).groups()
            k = cle(coeur)
            if len(k) < 4 or any(c.isdigit() for c in k) or (n == 1 and k in MOTS_COURANTS):
                continue
            # Sur un mot court, une seule lettre d'écart change déjà beaucoup (« still » / « TILL ») :
            # on exige une ressemblance plus forte.
            seuil = SEUIL if len(k) >= 7 else SEUIL_MOT_COURT
            trouve = process.extractOne(k, cles, scorer=fuzz.ratio, score_cutoff=seuil)
            if not trouve:
                continue
            officiel, categorie = valeurs[trouve[2]]
            remplace = _casse(officiel, coeur)
            # Mot déjà juste : on ne le touche que pour rétablir des accents (« glycemie » -> « glycémie »),
            # jamais pour en retirer (« Paracétamol » reste tel quel face à la DCI « PARACETAMOL »).
            accents = lambda s: sum(not c.isascii() for c in s)  # noqa: E731
            if trouve[1] < 100 or accents(remplace) > accents(coeur):
                corrections.append({"avant": coeur, "apres": remplace, "categorie": categorie,
                                    "score": round(trouve[1])})
                bloc = debut + remplace + fin
            sortie.append(bloc)
            i += n
            break
        else:
            sortie.append(mots[i])
            i += 1
    return " ".join(sortie), corrections


def normaliser_date(texte: str) -> str | None:
    """« 12-3-26 », « 12/03/2026 » -> « 12/03/2026 » ; None si aucune date lisible."""
    m = re.search(r"(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2,4})", texte)
    if not m:
        return None
    jour, mois, annee = (int(v) for v in m.groups())
    if annee < 100:
        annee += 2000
    if not (1 <= jour <= 31 and 1 <= mois <= 12):
        return None
    return f"{jour:02d}/{mois:02d}/{annee}"
