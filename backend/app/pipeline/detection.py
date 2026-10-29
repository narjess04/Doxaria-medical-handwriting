"""Détection d'objets avec YOLOv8 : lignes de texte, cachet, champs du bulletin."""

import ast
from pathlib import Path

import numpy as np
from PIL import Image

from app.core import config

from . import modeles


def _nms(boites: np.ndarray, scores: np.ndarray, iou: float) -> list[int]:
    """Indices gardés par la suppression des non-maxima (boîtes x0, y0, x1, y1)."""
    ordre, gardes = scores.argsort()[::-1], []
    aires = (boites[:, 2] - boites[:, 0]) * (boites[:, 3] - boites[:, 1])
    while ordre.size:
        i, reste = ordre[0], ordre[1:]
        gardes.append(int(i))
        x0 = np.maximum(boites[i, 0], boites[reste, 0])
        y0 = np.maximum(boites[i, 1], boites[reste, 1])
        x1 = np.minimum(boites[i, 2], boites[reste, 2])
        y1 = np.minimum(boites[i, 3], boites[reste, 3])
        inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
        ordre = reste[inter / (aires[i] + aires[reste] - inter + 1e-9) <= iou]
    return gardes


def _detecter_onnx(chemin: Path, image: Image.Image, seuil: float, iou: float = 0.7) -> list[dict]:
    """Comme Ultralytics (letterbox, NMS par classe), avec onnxruntime seul."""
    session = modeles.session_onnx(chemin)
    meta = session.get_modelmeta().custom_metadata_map
    noms = ast.literal_eval(meta["names"])
    cote = ast.literal_eval(meta.get("imgsz", "[640, 640]"))[0]

    # Letterbox : image réduite sans déformation, centrée sur un fond gris (114).
    image = image.convert("RGB")
    r = min(cote / image.width, cote / image.height)
    w, h = round(image.width * r), round(image.height * r)
    dx, dy = (cote - w) / 2, (cote - h) / 2
    fond = Image.new("RGB", (cote, cote), (114, 114, 114))
    fond.paste(image.resize((w, h), Image.BILINEAR), (round(dx - 0.1), round(dy - 0.1)))
    x = (np.asarray(fond, dtype=np.float32) / 255).transpose(2, 0, 1)[None]

    with modeles.verrou(str(chemin)):
        sortie = session.run(None, {session.get_inputs()[0].name: x})[0][0].T  # (8400, 4 + classes)
    scores = sortie[:, 4:]
    classes, confiances = scores.argmax(1), scores.max(1)
    garde = confiances >= seuil
    centres, classes, confiances = sortie[garde, :4], classes[garde], confiances[garde]
    if not len(confiances):
        return []
    boites = np.column_stack([centres[:, 0] - centres[:, 2] / 2, centres[:, 1] - centres[:, 3] / 2,
                              centres[:, 0] + centres[:, 2] / 2, centres[:, 1] + centres[:, 3] / 2])
    # NMS par classe : chaque classe est décalée pour que deux classes ne se suppriment pas.
    gardes = _nms(boites + classes[:, None] * cote * 2, confiances, iou)[:300]
    boites = ((boites[gardes] - [dx, dy, dx, dy]) / r).clip(0, [image.width, image.height] * 2)
    return [{"classe": noms[int(c)], "confiance": round(float(p), 4), "bbox": [round(float(v), 1) for v in b]}
            for c, p, b in zip(classes[gardes], confiances[gardes], boites)]


def detecter(chemin_modele: Path, image: Image.Image, seuil: float = config.SEUIL_DETECTION) -> list[dict]:
    """[{classe, confiance, bbox: [x0, y0, x1, y1]}], des plus confiantes aux moins confiantes."""
    if onnx := modeles.version_onnx(chemin_modele):
        return sorted(_detecter_onnx(onnx, image, seuil), key=lambda b: -b["confiance"])
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
