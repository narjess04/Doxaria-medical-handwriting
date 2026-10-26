"""Réponses sans modèle de langage, à partir des seuls référentiels (repli)."""

import re

from .referentiels import chercher_dci, chercher_medicament, chercher_terme, cle, medicaments_dans

AVERTISSEMENT = "Information issue des référentiels officiels. Elle ne remplace pas l'avis d'un médecin ou d'un pharmacien."

SALUTATIONS = {"BONJOUR", "SALUT", "BONSOIR", "HELLO", "AHLA", "SALEM"}

AIDE = {
    "texte": "Je peux vous renseigner sur un médicament commercialisé en Tunisie ou sur une "
             "abréviation médicale. Essayez par exemple :",
    "suggestions": ["Augmentin", "C'est quoi la NFS ?", "Doliprane est-il remboursé ?", "Que veut dire ATCD ?"],
}


def _fiche(m):
    lignes = []
    if m["dci"]:
        lignes.append(("Principe actif (DCI)", m["dci"]))
    if m["classe"]:
        lignes.append(("Classe thérapeutique", m["classe"] + (f" — {m['sous_classe']}" if m["sous_classe"] else "")))
    if m["type"]:
        lignes.append(("Type", m["type"]))
    presentations = sorted(set(m["presentations"]))
    if presentations:
        suite = f" (+{len(presentations) - 4} autres)" if len(presentations) > 4 else ""
        lignes.append(("Présentations", " · ".join(presentations[:4]) + suite))
    if m["laboratoire"]:
        lignes.append(("Laboratoire", m["laboratoire"]))
    remboursement = "Oui, par la CNAM" if m["rembourse"] else "Non remboursé par la CNAM"
    if m["prix"]:
        remboursement += f" · prix public {m['prix']:.3f} DT".replace(".", ",")
    lignes.append(("Remboursement", remboursement))
    if m["veic"]:
        lignes.append(("Classement VEIC", m["veic"]))
    return lignes


def repondre(question):
    """Réponse structurée : {texte, fiche?, suggestions?, source?}."""
    q = question.strip()
    if not q:
        return AIDE
    if set(cle(q).split()) & SALUTATIONS and len(q.split()) <= 3:
        return {"texte": "Bonjour ! " + AIDE["texte"], "suggestions": AIDE["suggestions"]}

    # Une abréviation explicitement demandée passe avant les noms de médicaments.
    demande_terme = re.search(r"(veut dire|signifie|c'?est quoi|qu'?est.ce que|définition)", q, re.I)
    terme = chercher_terme(q)
    if terme and (demande_terme or len(q.split()) <= 2):
        sens = terme["signification"] or terme["categorie"].replace("_", " ")
        return {"texte": f"{terme['terme']} : {sens}.",
                "categorie": terme["categorie"].replace("_", " "),
                "source": "Référentiel des termes médicaux" + (" (MSF)" if terme["source"] == "MSF" else "")}

    # Un nom commercial exact passe avant la DCI (« Augmentin » plutôt qu'« amoxicilline »).
    exact = medicaments_dans(q)
    dci = None if exact else chercher_dci(q)
    if dci:
        nom, marques = dci
        liste = ", ".join(marques[:12]) + (f" et {len(marques) - 12} autres" if len(marques) > 12 else "")
        return {"titre": nom.capitalize(),
                "texte": f"Principe actif (DCI) présent dans {len(marques)} médicament"
                         f"{'s' if len(marques) > 1 else ''} commercialisé{'s' if len(marques) > 1 else ''} "
                         f"en Tunisie : {liste}. Demandez-moi l'un de ces noms pour sa fiche.",
                "source": "Liste des AMM (DPM) et liste des médicaments remboursés (CNAM)"}

    m = exact[0] if exact else chercher_medicament(q)
    if m:
        return {"titre": m["nom"], "fiche": _fiche(m), "texte": AVERTISSEMENT,
                "source": "Liste des AMM (DPM) et liste des médicaments remboursés (CNAM)"}
    if terme:
        sens = terme["signification"] or terme["categorie"].replace("_", " ")
        return {"texte": f"{terme['terme']} : {sens}.", "source": "Référentiel des termes médicaux"}
    return {"texte": "Je n'ai trouvé ni médicament ni terme médical correspondant. " + AIDE["texte"],
            "suggestions": AIDE["suggestions"]}
