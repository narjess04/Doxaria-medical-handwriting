# Référentiel des médicaments commercialisés en Tunisie

Ce dossier contient la liste des médicaments à usage humain autorisés et
remboursés en Tunisie. Elle est construite **uniquement à partir de données
publiques d'organismes officiels tunisiens** : aucun nom n'a été saisi ou
généré à la main.

Dans Doxaria, ce référentiel sert à deux choses :

1. **Générer les données d'entraînement** de TrOCR : des images synthétiques
   de noms de médicaments réellement prescrits en Tunisie.
2. **Corriger les sorties de l'OCR** : un nom mal lu (« Augmantin ») est
   rapproché du nom officiel le plus proche (« AUGMENTIN ») par recherche floue
   dans le lexique.

## En bref

| | |
|---|---|
| Présentations autorisées (AMM DPM) | **6 053** |
| Présentations remboursées (CNAM) | **3 283** |
| Noms commerciaux uniques | **3 614** |
| DCI (principes actifs) uniques | **1 185** |
| Laboratoires | 436 |
| Classes thérapeutiques | 14 |

## Sources

### 1. Liste des AMM : DPM

| | |
|---|---|
| Organisme | Direction de la Pharmacie et du Médicament (DPM), Ministère de la Santé. Le site renvoie aussi à l'ANMPS (Agence Nationale du Médicament et des Produits de Santé). |
| URL | <https://dpm.tn/images/pdf/liste_amm.xls> |
| Page d'origine | <https://dpm.tn/medicament/humain/liste-des-medicaments> (lien « liste des AMM ») |
| Fichier local | `raw/dpm_liste_amm.xls` (3 855 360 octets) |
| SHA-256 | `e804c74db7a91097c7ee6d8f935ab8b1f5a652118a69233e238941efd420ccd6` |
| En-tête `Last-Modified` du serveur | 29/07/2025 |
| Dernier enregistrement du fichier (métadonnées Excel) | 19/01/2024, par l'utilisateur « Dpm10 » |
| AMM couvertes | du 08/09/1987 au 09/01/2024 |
| Téléchargé le | 26/10/2026 |

C'est la **liste officielle des Autorisations de Mise sur le Marché** pour les
médicaments à usage humain. Chaque ligne est une présentation : nom, dosage,
forme, conditionnement, DCI, classe et sous-classe thérapeutiques, laboratoire,
numéro et date d'AMM, tableau, statut générique/princeps/biosimilaire et
classement VEIC (Vital, Essentiel, Intermédiaire, Confort).

> **Fraîcheur des données** : le serveur indique une mise en ligne en juillet
> 2025, mais d'après les métadonnées du fichier et la date d'AMM la plus récente,
> le contenu est un **instantané de janvier 2024**. Les AMM accordées depuis n'y
> figurent pas. La liste CNAM ci-dessous, datée de juillet 2025, couvre une
> partie de ces nouveautés.

### 2. Liste des médicaments remboursés : CNAM

| | |
|---|---|
| Organisme | Caisse Nationale d'Assurance Maladie (CNAM) |
| Document | « Liste des médicaments classés en V, E, I couverts par le régime de base », mise à jour du 30/07/2025 |
| URL de téléchargement | <https://spot.tn/media/articles/LISTE%20DES%20MEDICAMENTS%20CLASSES%20EN%20V%20E%20I%20COUVERTS%20PAR%20LE%20REGIME%20DE%20BASE%2030-07-2025.xls> |
| Référencé par | <https://ballouchi.github.io/medoc/cnam-2025-08.html> |
| Fichier local | `raw/cnam_rembourses_2025-07-30.xls` (576 000 octets) |
| SHA-256 | `7071b581d2a4e47b07b3fa41af10aaa3b569b9894b0ca2de8b1106978bcfb411` |
| Téléchargé le | 26/10/2026 |

Chaque ligne donne le code PCT (Pharmacie Centrale de Tunisie), le libellé
commercial complet, le prix public, le tarif de référence CNAM, la catégorie
(V, E ou I), la DCI et la nécessité d'un accord préalable.

> **Provenance** : ce fichier est un export de la CNAM, mais il a été récupéré
> sur un site relais (spot.tn), pas directement sur cnam.nat.tn. Son contenu
> (codes PCT, prix, DCI) est cohérent avec la liste DPM : 2 864 des 3 283
> présentations ont un nom commercial présent dans la liste des AMM.

## Fichiers générés

Tous les fichiers sont en UTF-8 et sont produits par
[`scripts/build_medicaments.py`](../../scripts/build_medicaments.py) à partir
des deux fichiers de `raw/`.

### `medicaments_tn.csv` : 6 053 lignes

Une ligne par présentation de la liste DPM.

| Colonne | Description |
|---|---|
| `nom` | Nom commercial (ex. `AUGMENTIN`) |
| `dosage` | Dosage (ex. `1g/125mg`). Vide pour 545 lignes, comme dans la source |
| `forme` | Forme galénique (ex. `Poudre pour suspension orale`) |
| `presentation` | Conditionnement (ex. `B/24 Sachets-doses`) |
| `dci` | Dénomination Commune Internationale |
| `classe`, `sous_classe` | Classe thérapeutique |
| `laboratoire` | Titulaire de l'AMM |
| `amm`, `date_amm` | Numéro et date de l'AMM |
| `tableau` | Tableau réglementaire (A, B, C ou O), tel que dans la source |
| `type` | Générique (4 160), Princeps (1 863) ou Biosimilaire (30) |
| `veic` | Vital (880), Essentiel (4 050), Intermédiaire (444), Confort (616) |
| `rembourse_cnam` | `True` si le nom commercial figure dans la liste CNAM (3 123 lignes) |

### `cnam_rembourses.csv` : 3 283 lignes

La liste CNAM nettoyée, avec les colonnes `code_pct`, `nom_commercial`
(libellé d'origine), `nom` (nom commercial extrait), `prix_public`,
`tarif_reference`, `categorie`, `dci`, `accord_prealable` et `dans_dpm` (le nom
existe dans la liste des AMM).

### `lexique_noms.txt` : 3 614 noms

Noms commerciaux uniques, en majuscules et sans accents : les 3 328 noms de la
DPM, plus ceux de la CNAM absents de la DPM.

### `lexique_dci.txt` : 1 185 DCI

Principes actifs uniques, issus des deux sources.

## Traitement appliqué

Le script ne fait que nettoyer et rapprocher les deux sources. Il n'invente
aucune donnée :

1. **Nettoyage** : suppression des retours à la ligne et des espaces multiples
   dans les cellules. Les colonnes longues sans intérêt pour l'OCR (indications,
   conditionnement primaire, durée de conservation) sont écartées. Les doublons
   stricts (6 lignes) sont supprimés.
2. **Extraction du nom commercial CNAM** : les libellés CNAM mêlent nom, forme
   et dosage (`DEPAKINE Comp Gastroresistant 500mg Bt 50`). Le nom est d'abord
   recherché parmi les noms DPM (le plus long qui préfixe le libellé). Sinon, il
   est coupé avant le premier mot de forme (`Comp`, `Gélule`, `Sol`…) ou le
   premier nombre.
3. **Rapprochement** : une présentation DPM est marquée `rembourse_cnam` si son
   nom commercial figure dans la liste CNAM.
4. **Lexiques** : union des noms et des DCI, normalisés en majuscules sans
   accents.

## Limites connues

- **Instantané DPM de janvier 2024** : voir la section sur la fraîcheur des
  données plus haut.
- **419 présentations CNAM sans AMM correspondante** : AMM retirées ou noms
  orthographiés différemment selon les deux organismes. Leurs noms sont gardés
  dans le lexique, puisqu'un médecin peut encore les prescrire.
- **Extraction heuristique** pour ces 419 libellés : quelques variantes d'un
  même produit restent séparées (ex. `PARACETAMOL I` et `PARACETAMOL I PS`).
  Pour la correction floue, c'est sans conséquence.
- **Hors périmètre** : les produits sans AMM de médicament (compléments
  alimentaires, parapharmacie, dispositifs médicaux) ne sont pas inclus, même
  s'ils apparaissent parfois sur des ordonnances.

## Vérifier et reproduire

Contrôler que les fichiers sources n'ont pas été modifiés :

```bash
sha256sum raw/*.xls
```

Régénérer les fichiers à partir des sources (dépendances : `pandas`, `xlrd`) :

```bash
python scripts/build_medicaments.py
```

Comparer avec la version en ligne actuelle de la DPM :

```bash
curl -L -o liste_amm_actuelle.xls https://dpm.tn/images/pdf/liste_amm.xls
sha256sum liste_amm_actuelle.xls
```

Si l'empreinte diffère, la DPM a publié une nouvelle version. Remplacer le
fichier dans `raw/`, relancer le script et mettre à jour ce README.
