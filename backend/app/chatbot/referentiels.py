"""Référentiels officiels : médicaments (DPM + CNAM) et termes médicaux.

Chargés une fois depuis data/ à la racine du projet. Servent à vérifier les
médicaments lus sur une ordonnance et à répondre dans l'assistant.
"""

import csv
import difflib
import re
import unicodedata
from functools import lru_cache

from app.core.config import DATA_DIR


def cle(texte):
    """Majuscules sans accents ni ponctuation, pour comparer des noms."""
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", texte.upper()).strip()


@lru_cache(maxsize=1)
def medicaments():
    """nom normalisé -> fiche (présentations DPM, DCI, classe, remboursement)."""
    fiches = {}
    with open(DATA_DIR / "medicaments" / "medicaments_tn.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fiche = fiches.setdefault(cle(r["nom"]), {
                "nom": r["nom"], "dci": r["dci"], "classe": r["classe"].capitalize(),
                "sous_classe": r["sous_classe"].capitalize(), "laboratoire": r["laboratoire"],
                "type": r["type"], "veic": r["veic"], "rembourse": r["rembourse_cnam"] == "True",
                "presentations": [], "prix": None,
            })
            fiche["presentations"].append(" ".join(filter(None, [r["dosage"], r["forme"]])))
    with open(DATA_DIR / "medicaments" / "cnam_rembourses.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fiche = fiches.get(cle(r["nom"]))
            if fiche is None:  # remboursé par la CNAM mais absent de la liste DPM
                fiche = fiches[cle(r["nom"])] = {
                    "nom": r["nom"], "dci": r["dci"], "classe": "", "sous_classe": "",
                    "laboratoire": "", "type": "", "veic": "", "rembourse": True,
                    "presentations": [r["nom_commercial"]], "prix": None,
                }
            if fiche["prix"] is None and r["prix_public"]:
                fiche["prix"] = float(r["prix_public"])
    return fiches


@lru_cache(maxsize=1)
def termes():
    """terme normalisé -> {terme, signification, categorie}."""
    with open(DATA_DIR / "termes_medicaux" / "termes_medicaux.csv", encoding="utf-8") as f:
        return {cle(r["terme"]): r for r in csv.DictReader(f) if cle(r["terme"])}


@lru_cache(maxsize=1)
def _index_noms():
    noms = medicaments()
    return noms, max(len(n.split()) for n in noms)


def medicaments_dans(texte):
    """Médicaments du référentiel cités dans un texte (groupes de 1 à 4 mots)."""
    noms, n_max = _index_noms()
    mots = cle(texte).split()
    trouves, i = [], 0
    while i < len(mots):
        for n in range(min(n_max, len(mots) - i), 0, -1):
            groupe = " ".join(mots[i:i + n])
            if len(groupe) >= 3 and groupe in noms:
                trouves.append(noms[groupe])
                i += n
                break
        else:
            i += 1
    return trouves


def chercher_medicament(question):
    """Fiche du médicament le plus proche d'un nom tapé (tolère les fautes)."""
    trouves = medicaments_dans(question)
    if trouves:
        return trouves[0]
    noms = medicaments()
    for mot in sorted(cle(question).split(), key=len, reverse=True):
        if len(mot) >= 5:
            proches = difflib.get_close_matches(mot, noms.keys(), n=1, cutoff=0.86)
            if proches:
                return noms[proches[0]]
    return None


@lru_cache(maxsize=1)
def _index_dci():
    """DCI normalisée -> noms commerciaux qui la contiennent."""
    index = {}
    for fiche in medicaments().values():
        if fiche["dci"]:
            index.setdefault(cle(fiche["dci"]), set()).add(fiche["nom"])
    return index


def chercher_dci(question):
    """(DCI, noms commerciaux) si la question cite un principe actif."""
    index = _index_dci()
    q = cle(question)
    for dci in sorted(index, key=len, reverse=True):
        if len(dci) >= 4 and re.search(rf"\b{re.escape(dci)}\b", q):
            return dci, sorted(index[dci])
    # Variantes d'orthographe : la DPM écrit parfois à l'anglaise (« IBUPROFEN »).
    for mot in sorted(q.split(), key=len, reverse=True):
        if len(mot) >= 6:
            proches = difflib.get_close_matches(mot, index.keys(), n=1, cutoff=0.88)
            if proches:
                return proches[0], sorted(index[proches[0]])
    return None


def chercher_terme(question):
    """Terme médical cité dans la question. Une abréviation courte (« TA », « SA »)
    doit être en majuscules ou former toute la question, pour ne pas confondre
    avec « ta », « sa » ou le « C » de « C'est »."""
    t = termes()
    mots = re.findall(r"[\wÀ-ÿ°/+-]+", question)
    for mot in sorted(mots, key=len, reverse=True):
        k = cle(mot)
        if k not in t or len(k) < 2:
            continue
        if len(k) <= 3 and not (mot.isupper() or len(mots) == 1):
            continue
        return t[k]
    return None


def statistiques():
    m = medicaments()
    return {
        "noms": len(m),
        "presentations": sum(len(f["presentations"]) for f in m.values()),
        "termes": len(termes()),
    }
