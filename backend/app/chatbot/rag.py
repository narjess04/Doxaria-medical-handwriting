"""RAG de l'assistant médical.

1. Recherche : on repère dans la conversation les médicaments, DCI et termes
   médicaux, et on récupère leurs fiches dans les référentiels officiels
   (noms commerciaux tunisiens, DCI, classe, remboursement CNAM, prix).
2. Génération : ces fiches sont données au modèle de langage avec la question ;
   il complète avec ses connaissances (effets indésirables, interactions…).

Si le modèle n'est pas configuré ou ne répond pas, on se replie sur des
réponses construites à partir des seuls référentiels (module repli).
"""

import logging

import requests

from app.core import config

from .referentiels import chercher_dci, chercher_medicament, chercher_terme, medicaments_dans
from .repli import repondre as repondre_sans_llm

log = logging.getLogger(__name__)

SYSTEME = """Tu es l'assistant médical de MediTrust, une plateforme tunisienne qui numérise les ordonnances.
Tu t'adresses à des patients, des pharmaciens et des médecins. Réponds toujours en français, de façon
claire, structurée et concise (Markdown : titres courts, listes, tableaux si utile). Pas de longue introduction.

Ce que tu fais :
- Informer sur les médicaments : indications, posologie usuelle chez l'adulte, effets indésirables
  (fréquents puis graves), contre-indications, interactions, précautions (grossesse, allaitement,
  enfant, sujet âgé, insuffisance rénale ou hépatique), conservation.
- Pour une liste de médicaments (par exemple une ordonnance), indiquer à quoi sert chacun et quelles
  pathologies ou situations cette association évoque habituellement. Présente-les comme des
  HYPOTHÈSES (« ces médicaments sont souvent prescrits pour… »), jamais comme un diagnostic certain.
  Signale les interactions ou redondances notables (deux AINS, deux paracétamols…).
- Expliquer les abréviations et examens médicaux.

Règles :
- Utilise en priorité les données du « Référentiel officiel tunisien » fournies dans le message
  système suivant : noms commerciaux, DCI, dosages, remboursement CNAM et prix. Ne les invente pas.
  Si un médicament n'y figure pas, dis qu'il n'est pas dans le référentiel tunisien.
- Tu ne poses pas de diagnostic définitif et tu ne modifies jamais un traitement prescrit :
  renvoie vers le médecin ou le pharmacien pour toute décision.
- Si des signes d'urgence sont décrits (difficulté à respirer, gonflement du visage, douleur
  thoracique, malaise, saignement important, idées suicidaires…), dis d'appeler le SAMU (190)
  immédiatement, avant toute autre information.
- Si tu ne sais pas, dis-le. Si la question n'a rien de médical, recentre poliment.
- Termine par une courte phrase rappelant de demander l'avis d'un professionnel de santé
  quand la réponse touche à un traitement."""

SOURCE = "Référentiel officiel tunisien (DPM, CNAM) + modèle de langage"


def llm_configure():
    return bool(config.LLM_API_KEY)


def _fiche(m):
    lignes = [f"- {m['nom']} : DCI {m['dci'] or 'inconnue'}"]
    if m["classe"]:
        lignes.append(f"  classe : {m['classe']}" + (f" / {m['sous_classe']}" if m["sous_classe"] else ""))
    presentations = sorted(set(m["presentations"]))
    if presentations:
        lignes.append("  présentations : " + " ; ".join(presentations[:6]))
    if m["type"]:
        lignes.append(f"  type : {m['type']}")
    lignes.append("  remboursé CNAM : " + ("oui" if m["rembourse"] else "non")
                  + (f", prix public {m['prix']:.3f} DT" if m["prix"] else ""))
    return "\n".join(lignes)


def rechercher(textes):
    """Étape de recherche : (noms des médicaments trouvés, extraits du référentiel)."""
    fiches, dcis, termes = {}, {}, {}
    for texte in textes:
        trouves = medicaments_dans(texte) or [m for m in [chercher_medicament(texte)] if m]
        for m in trouves:
            fiches.setdefault(m["nom"], m)
        if not trouves:
            dci = chercher_dci(texte)
            if dci:
                dcis[dci[0]] = dci[1]
        terme = chercher_terme(texte)
        if terme:
            termes[terme["terme"]] = terme
    parties = []
    if fiches:
        parties.append("Médicaments cités :\n" + "\n".join(_fiche(m) for m in list(fiches.values())[:8]))
    for dci, marques in list(dcis.items())[:3]:
        parties.append(f"La DCI {dci} est commercialisée en Tunisie sous : {', '.join(marques[:15])}"
                       + (f" (+{len(marques) - 15})" if len(marques) > 15 else ""))
    for t in termes.values():
        parties.append(f"Terme {t['terme']} : {t['signification'] or t['categorie']}")
    return list(fiches), "\n\n".join(parties)


def generer(question, historique, extraits):
    """Étape de génération : appel au modèle de langage (API compatible OpenAI)."""
    messages = [
        {"role": "system", "content": SYSTEME},
        {"role": "system", "content": "Référentiel officiel tunisien (DPM, CNAM) :\n"
         + (extraits or "aucun médicament ni terme du référentiel reconnu dans la question.")},
        *historique,
        {"role": "user", "content": question},
    ]
    corps = {"model": config.LLM_MODEL, "messages": messages, "temperature": 0.3, "max_completion_tokens": 1200}
    if "gpt-oss" in config.LLM_MODEL:
        corps["reasoning_effort"] = "low"  # modèle à raisonnement : réponse rapide
    r = requests.post(config.LLM_BASE_URL.rstrip("/") + "/chat/completions",
                      headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                      json=corps, timeout=config.LLM_TIMEOUT)
    r.raise_for_status()
    texte = r.json()["choices"][0]["message"]["content"].strip()
    if not texte:
        raise ValueError("réponse vide")
    return texte


def repondre(question, historique):
    """Réponse de l'assistant : Markdown du modèle, ou repli sur les référentiels."""
    if llm_configure():
        # La recherche tient compte des derniers messages (« et ses effets ? »).
        textes = [m["content"] for m in historique if m["role"] == "user"][-3:] + [question]
        medicaments, extraits = rechercher(textes)
        try:
            return {"markdown": generer(question, historique, extraits), "medicaments": medicaments,
                    "source": SOURCE}
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            log.warning("Modèle de langage indisponible, repli sur les référentiels : %s", e)
    return repondre_sans_llm(question)
