"""Détection d'objets avec YOLOv8 : lignes de texte, cachet, champs du bulletin."""

from pathlib import Path

from PIL import Image

from app.core import config

from . import modeles


def detecter(chemin_modele: Path, image: Image.Image, seuil: float = config.SEUIL_DETECTION) -> list[dict]:
    """[{classe, confiance, bbox: [x0, y0, x1, y1]}], des plus confiantes aux moins confiantes."""
    modele = modeles.yolo(chemin_modele)
    with modeles.verrou(str(chemin_modele)):
        res = modele.predict(image, conf=seuil, verbose=False)[0]
    boites = [
        {"classe": res.names[int(c)], "confiance": round(float(p), 4), "bbox": [round(float(v), 1) for v in xyxy]}
        for c, p, xyxy in zip(res.boxes.cls.tolist(), res.boxes.conf.tolist(), res.boxes.xyxy.tolist())
    ]
    return sorted(boites, key=lambda b: -b["confiance"])


def meilleure(boites: list[dict], classe: str) -> dict | None:
    return next((b for b in boites if b["classe"] == classe), None)


def _aire(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersection(a, b):
    return _aire((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def dedoublonner(boites: list[dict], recouvrement: float = 0.6) -> list[dict]:
    """Retire les boîtes recouvertes à plus de `recouvrement` par une boîte plus confiante."""
    gardees = []
    for b in sorted(boites, key=lambda b: -b["confiance"]):
        if all(_intersection(b["bbox"], g["bbox"]) < recouvrement * min(_aire(b["bbox"]), _aire(g["bbox"]))
               for g in gardees):
            gardees.append(b)
    return gardees


def regrouper_en_lignes(boites: list[dict], ecart_max: float = 3.0) -> list[dict]:
    """Fusionne les morceaux d'une même ligne, dans l'ordre de lecture.

    Deux boîtes sont sur la même ligne si elles se chevauchent verticalement sur au
    moins la moitié de la plus petite. Un écart horizontal de plus de `ecart_max`
    hauteurs de ligne sépare deux blocs (ex. date à droite, nom à gauche).
    """
    lignes = []  # chaque ligne : liste de boîtes, triées de gauche à droite
    for b in sorted(boites, key=lambda b: (b["bbox"][1] + b["bbox"][3]) / 2):
        x0, y0, x1, y1 = b["bbox"]
        for ligne in lignes:
            ly0, ly1 = min(m["bbox"][1] for m in ligne), max(m["bbox"][3] for m in ligne)
            commun = min(y1, ly1) - max(y0, ly0)
            if commun >= 0.5 * min(y1 - y0, ly1 - ly0):
                ligne.append(b)
                break
        else:
            lignes.append([b])

    blocs = []
    for ligne in lignes:
        ligne.sort(key=lambda m: m["bbox"][0])
        hauteur = max(m["bbox"][3] for m in ligne) - min(m["bbox"][1] for m in ligne)
        bloc = [ligne[0]]
        for m in ligne[1:]:
            if m["bbox"][0] - max(n["bbox"][2] for n in bloc) > ecart_max * hauteur:
                blocs.append(bloc)
                bloc = []
            bloc.append(m)
        blocs.append(bloc)

    fusion = [{
        "classe": bloc[0]["classe"],
        "confiance": max(m["confiance"] for m in bloc),
        "bbox": [min(m["bbox"][0] for m in bloc), min(m["bbox"][1] for m in bloc),
                 max(m["bbox"][2] for m in bloc), max(m["bbox"][3] for m in bloc)],
    } for bloc in blocs]
    return sorted(fusion, key=lambda b: (b["bbox"][1], b["bbox"][0]))


def lignes(image: Image.Image) -> list[dict]:
    """Lignes de texte dans l'ordre de lecture (de haut en bas, puis de gauche à droite).

    Le détecteur de l'ancienne version renvoie souvent des morceaux de mots qui se
    chevauchent ; TrOCR a besoin de lignes entières : on dédoublonne puis on regroupe.
    """
    return regrouper_en_lignes(dedoublonner(detecter(config.MODELE_LIGNES, image)))
