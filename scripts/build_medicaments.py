"""Construit le dataset des médicaments commercialisés en Tunisie.

Sources (dans data/medicaments/raw/) :
- dpm_liste_amm.xls : liste officielle des AMM de la DPM
  (https://dpm.tn/images/pdf/liste_amm.xls)
- cnam_rembourses_2025-07-30.xls : médicaments remboursés par la CNAM
  (régime de base, mise à jour du 30/07/2025)

Sorties (dans data/medicaments/) :
- medicaments_tn.csv     une ligne par présentation (AMM DPM)
- cnam_rembourses.csv    liste CNAM nettoyée, avec le nom commercial extrait
- lexique_noms.txt       noms commerciaux uniques (DPM + CNAM)
- lexique_dci.txt        DCI uniques

Usage : python scripts/build_medicaments.py
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "medicaments"
RAW_DIR = DATA_DIR / "raw"
DPM_FILE = RAW_DIR / "dpm_liste_amm.xls"
CNAM_FILE = RAW_DIR / "cnam_rembourses_2025-07-30.xls"

DPM_COLUMNS = {
    "Nom": "nom",
    "Dosage": "dosage",
    "Forme": "forme",
    "Présentation": "presentation",
    "DCI": "dci",
    "Classe": "classe",
    "Sous Classe": "sous_classe",
    "Laboratoire": "laboratoire",
    "AMM": "amm",
    "Date AMM": "date_amm",
    "tableau": "tableau",
    "G/P/B": "type",
    "VEIC": "veic",
}

CNAM_COLUMNS = {
    "CODE_PCT": "code_pct",
    "NOM_COMMERCIAL": "nom_commercial",
    "PRIX_PUBLIC": "prix_public",
    "TARIF_REFERENCE": "tarif_reference",
    "CATEGORIE": "categorie",
    "DCI": "dci",
    "AP": "accord_prealable",
}

# Premiers mots d'une forme ou d'un conditionnement dans les libellés CNAM :
# le nom commercial s'arrête juste avant.
FORME_TOKENS = {
    "AD", "ADULTE", "AMP", "B", "BT", "BUV", "CAPS", "CAPSULE", "CO", "COLLY",
    "COLLYRE", "COMP", "CP", "CPR", "CREME", "DERM", "EMUL", "ENF", "ENFANT",
    "FL", "GEL", "GELULE", "GEULE", "GLES", "GOUT", "GOUTTES", "GRAND",
    "GRANULE", "GRANULES", "GTTE", "GTTES", "INJ", "LOTION", "LYOPH", "NOUR",
    "NOURRISSON", "NOURRISSONS", "OVULE", "P", "PATCH", "PDE", "PDRE", "POM",
    "POMMADE", "PPI", "SACH", "SACHET", "SIROP", "SOL", "SPRAY", "SUPP",
    "SUPPO", "SUSP", "TB", "TBE",
}


def clean(value):
    """Supprime retours chariot et espaces multiples."""
    if pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize(text):
    """Majuscules sans accents, pour comparer les noms."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.upper()).strip()


def load_dpm():
    df = pd.read_excel(DPM_FILE, dtype=str)[list(DPM_COLUMNS)].rename(columns=DPM_COLUMNS)
    df = df.apply(lambda col: col.map(clean))
    df["date_amm"] = pd.to_datetime(df["date_amm"], errors="coerce").dt.date
    df = df.dropna(subset=["nom"]).drop_duplicates()
    return df.sort_values(["nom", "dosage", "forme"]).reset_index(drop=True)


def extract_brand(label, known_brands):
    """Nom commercial d'un libellé CNAM (ex. « DEPAKINE Comp ... 500mg Bt 50 »)."""
    norm = normalize(label)
    for brand in known_brands:
        if norm == brand or norm.startswith(brand + " "):
            return brand
    # « (EX WINTHROP) » : ancien nom du laboratoire, pas le nom commercial.
    label = re.sub(r"\(\s*ex\b.*", "", label, flags=re.IGNORECASE)
    words = []
    for word in label.split():
        token = normalize(word).split("/")[0].replace(".", "")
        # « E CAPS », « VIT D3 » : on ne coupe pas après une seule lettre,
        # ni sur un mot comme « D3 » qui fait partie du nom.
        is_forme = token in FORME_TOKENS and len("".join(words)) > 1
        if word[0].isdigit() or is_forme:
            break
        words.append(word)
    return normalize(" ".join(words)) if words else normalize(label.split()[0])


def load_cnam(dpm_brands):
    df = pd.read_excel(CNAM_FILE, dtype=str)[list(CNAM_COLUMNS)].rename(columns=CNAM_COLUMNS)
    df = df.apply(lambda col: col.map(clean))
    for col in ("prix_public", "tarif_reference"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["accord_prealable"] = df["accord_prealable"].eq("O")
    # Les noms les plus longs d'abord, pour « CO-OLMETEC » avant « OLMETEC ».
    known = sorted(dpm_brands, key=len, reverse=True)
    df.insert(2, "nom", df["nom_commercial"].map(lambda s: extract_brand(s, known)))
    df["dans_dpm"] = df["nom"].isin(dpm_brands)
    return df.sort_values(["nom", "nom_commercial"]).reset_index(drop=True)


def write_lexicon(path, values):
    items = sorted({v for v in values if v}, key=str.casefold)
    path.write_text("\n".join(items) + "\n", encoding="utf-8")
    return len(items)


def main():
    dpm = load_dpm()
    dpm_brands = set(dpm["nom"].map(normalize))

    cnam = load_cnam(dpm_brands)
    dpm["rembourse_cnam"] = dpm["nom"].map(normalize).isin(set(cnam["nom"]))

    dpm.to_csv(DATA_DIR / "medicaments_tn.csv", index=False, encoding="utf-8")
    cnam.to_csv(DATA_DIR / "cnam_rembourses.csv", index=False, encoding="utf-8")

    n_noms = write_lexicon(DATA_DIR / "lexique_noms.txt", dpm_brands | set(cnam["nom"]))
    n_dci = write_lexicon(
        DATA_DIR / "lexique_dci.txt",
        pd.concat([dpm["dci"], cnam["dci"]]).dropna().map(normalize),
    )

    print(f"DPM  : {len(dpm)} présentations, {len(dpm_brands)} noms commerciaux")
    print(f"CNAM : {len(cnam)} présentations, {(~cnam['dans_dpm']).sum()} absentes de la DPM")
    print(f"Lexiques : {n_noms} noms commerciaux, {n_dci} DCI")


if __name__ == "__main__":
    main()
