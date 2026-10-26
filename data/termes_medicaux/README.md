# Termes médicaux courants

Vocabulaire médical français qu'on retrouve le plus souvent sur les
ordonnances, les bilans et les comptes rendus : abréviations de posologie,
voies d'administration, unités, examens, pathologies, signes cliniques, classes
thérapeutiques et termes de chirurgie.

Dans Doxaria, ce fichier sert à :

1. **Générer les données d'entraînement** : en plus des noms de médicaments,
   les lignes synthétiques contiennent ce vocabulaire (« ATCD : HTA, DT2 »,
   « Bilan : NFS, CRP, GAJ », « 1 cp x3/j »…). Le modèle apprend ainsi à lire
   les abréviations des médecins.
2. **Mesurer la reconnaissance du vocabulaire médical** : le notebook de
   comparaison calcule le taux de termes médicaux correctement lus.
3. **Corriger les sorties de l'OCR**, avec le lexique des médicaments.

## Contenu de `termes_medicaux.csv` : 262 termes

| Colonne | Description |
|---|---|
| `terme` | Le terme tel qu'il est écrit (ex. `NFS`, `x3/j`, `cœlioscopie`) |
| `signification` | Forme développée pour une abréviation ; vide pour un mot courant |
| `categorie` | Voir le tableau ci-dessous |
| `source` | `MSF` ou `usage_courant` (voir Sources) |

| Catégorie | Termes | Exemples |
|---|---|---|
| `pathologie` | 54 | ATCD, HTA, DT2, BPCO, angine |
| `examen_biologique` | 52 | NFS, CRP, GAJ, HbA1c, ECBU |
| `posologie` | 31 | cp, x3/j, QSP, à jeun, LP |
| `signe_clinique` | 23 | TA, SpO2, T°, RAS, AEG |
| `chirurgie` | 23 | AG, cœlioscopie, exérèse, CRO |
| `classe_therapeutique` | 21 | AINS, IPP, HBPM, ATB |
| `examen_imagerie` | 18 | ECG, TDM, IRM, FOGD |
| `unite` | 17 | mg, UI, g/L, mmol/L |
| `voie` | 13 | PO, IV, IM, SC |
| `administratif` | 10 | Dr, CNAM, APCI, RDV |

## Sources

- **`MSF`** (45 termes) : la liste « Abréviations, sigles et acronymes » du
  *Guide clinique et thérapeutique* de Médecins Sans Frontières,
  <https://medicalguidelines.msf.org/fr/viewport/CG/francais/sigles-et-abreviations-16689362.html>.
  Le terme et sa signification y figurent tels quels.
- **`usage_courant`** (217 termes) : liste établie à la main pour ce projet, à
  partir des abréviations et du vocabulaire couramment employés en médecine
  française. Les significations peuvent être vérifiées dans les listes
  d'abréviations médicales publiées, par exemple sur EM-consulte
  (<https://www.em-consulte.com/article/272769/abreviations>).

## Limites

- Ce n'est pas un référentiel officiel exhaustif, mais une sélection des termes
  les plus fréquents sur les documents visés par Doxaria.
- Certaines abréviations sont **ambiguës** selon le contexte (ex. `IC` =
  insuffisance cardiaque ou inhibiteur calcique, `TP` = taux de prothrombine).
  Une seule signification est retenue, celle de l'usage le plus courant sur
  les ordonnances et les bilans.
