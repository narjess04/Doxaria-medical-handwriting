"""Espace connecté : tableau de bord, extraction, historique, fraude, assistant."""

import base64
import json
import mimetypes
import uuid
from pathlib import Path

from flask import (Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_login import current_user, login_required

from . import db, services
from .models import TYPES_DOCUMENT, Document, maintenant

bp = Blueprint("outils", __name__)

EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")


@bp.before_request
@login_required
def connexion_requise():
    pass


def dossier_uploads():
    dossier = Path(current_app.instance_path) / "uploads"
    dossier.mkdir(exist_ok=True)
    return dossier


def enregistrer_image(fichier):
    """Enregistre l'image envoyée sous un nom aléatoire ; None si elle est invalide."""
    if not fichier or not fichier.filename:
        return None
    ext = fichier.filename.rsplit(".", 1)[-1].lower() if "." in fichier.filename else ""
    debut = fichier.stream.read(12)
    fichier.stream.seek(0)
    if ext not in EXTENSIONS or not debut.startswith(SIGNATURES):
        return None
    nom = f"{uuid.uuid4().hex}.{ext}"
    fichier.save(dossier_uploads() / nom)
    return nom


def document_de_l_utilisateur(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None or doc.user_id != current_user.id:
        abort(404)
    return doc


@bp.route("/espace")
def dashboard():
    docs = current_user.documents
    stats = {t: sum(d.type == t for d in docs) for t in TYPES_DOCUMENT}
    # Un seul appel au backend pour toutes les ordonnances ; None s'il ne répond pas.
    textes = "\n".join(d.texte for d in docs if d.type == "ordonnance")
    verifies = services.verifier_medicaments(textes) if textes else []
    return render_template("outils/dashboard.html", recents=docs[:5], stats=stats,
                           nb_medicaments=None if verifies is None else len(verifies))


@bp.route("/extraction", methods=["GET", "POST"])
def extraction():
    if request.method == "POST":
        nom = enregistrer_image(request.files.get("image"))
        if nom is None:
            flash("Choisissez une image JPG, PNG ou WebP.", "error")
            return redirect(url_for("outils.extraction"))
        type_document = request.form.get("type", "auto")
        if type_document not in ("auto", *TYPES_DOCUMENT):
            type_document = "auto"
        chemin = dossier_uploads() / nom
        if current_user.demo:
            # Compte démo : résultat affiché une seule fois, rien n'est enregistré ;
            # l'image est supprimée tout de suite et montrée depuis la mémoire.
            try:
                res = services.analyser_document(chemin, type_document)
                image = f"data:image/{chemin.suffix[1:].replace('jpg', 'jpeg')};base64,{base64.b64encode(chemin.read_bytes()).decode()}"
            finally:
                chemin.unlink(missing_ok=True)
            doc = Document(type=res["type"], image=nom, medecin=res["medecin"], texte=res["texte"],
                           numero=res["numero"], demo=res["demo"], boites=json.dumps(res.get("zones", [])),
                           date_document=res.get("date"), modele=res.get("modele"), created_at=maintenant())
            verifies = services.verifier_medicaments(doc.texte) if doc.type == "ordonnance" else []
            return render_template("outils/document.html", doc=doc, verifies=verifies, image_demo=image)
        try:
            res = services.analyser_document(chemin, type_document)
            image_data = chemin.read_bytes()
        finally:
            chemin.unlink(missing_ok=True)  # l'image est gardée en base, pas sur le disque
        doc = Document(user_id=current_user.id, type=res["type"], image=nom, image_data=image_data, medecin=res["medecin"],
                       texte=res["texte"], numero=res["numero"], demo=res["demo"], boites=json.dumps(res.get("zones", [])),
                       date_document=res.get("date"), modele=res.get("modele"))
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for("outils.document", doc_id=doc.id))
    return render_template("outils/extraction.html", types=TYPES_DOCUMENT)


@bp.route("/documents/<int:doc_id>", methods=["GET", "POST"])
def document(doc_id):
    doc = document_de_l_utilisateur(doc_id)
    if request.method == "POST":
        # Correction humaine du texte lu par l'OCR.
        doc.medecin = request.form.get("medecin", "").strip()[:200]
        doc.texte = request.form.get("texte", "").strip()
        doc.numero = request.form.get("numero", "").strip()[:50] or None
        doc.date_document = request.form.get("date_document", "").strip()[:20] or None
        db.session.commit()
        flash("Modifications enregistrées.", "success")
        return redirect(url_for("outils.document", doc_id=doc.id))
    verifies = services.verifier_medicaments(doc.texte) if doc.type == "ordonnance" else []
    return render_template("outils/document.html", doc=doc, verifies=verifies)


@bp.route("/documents/<int:doc_id>/supprimer", methods=["POST"])
def supprimer(doc_id):
    doc = document_de_l_utilisateur(doc_id)
    (dossier_uploads() / doc.image).unlink(missing_ok=True)
    db.session.delete(doc)
    db.session.commit()
    flash("Document supprimé.", "info")
    return redirect(url_for("outils.historique"))


@bp.route("/fichiers/<nom>")
def fichier(nom):
    # Seul le propriétaire du document peut voir son image.
    doc = Document.query.filter_by(image=nom, user_id=current_user.id).first()
    if doc is None:
        abort(404)
    if doc.image_data:
        return Response(doc.image_data, mimetype=mimetypes.guess_type(nom)[0] or "application/octet-stream",
                        headers={"Cache-Control": "private, max-age=86400"})
    return send_from_directory(dossier_uploads(), nom)


@bp.route("/historique")
def historique():
    filtre = request.args.get("type")
    docs = [d for d in current_user.documents if filtre not in TYPES_DOCUMENT or d.type == filtre]
    return render_template("outils/historique.html", docs=docs, filtre=filtre, types=TYPES_DOCUMENT)


@bp.route("/fraude")
def fraude():
    return render_template("outils/fraude.html")


@bp.route("/fraude/analyse", methods=["POST"])
def fraude_analyse():
    nom = enregistrer_image(request.files.get("image"))
    if nom is None:
        return jsonify(erreur="Choisissez une image JPG, PNG ou WebP."), 400
    chemin = dossier_uploads() / nom
    try:
        return jsonify(services.analyser_fraude(chemin))
    finally:
        chemin.unlink(missing_ok=True)  # l'image n'est pas conservée


@bp.route("/assistant")
def assistant():
    # « q » : bouton « Analyser avec l'assistant » ; « question » : formulaire envoyé sans JavaScript.
    question = request.args.get("q") or request.args.get("question") or ""
    return render_template("outils/assistant.html", etat=services.etat_backend(), question=question.strip()[:1000])


@bp.route("/assistant/question", methods=["POST"])
def assistant_question():
    # Relais vers le RAG du backend, qui valide la question et l'historique.
    donnees = request.get_json(silent=True) or {}
    question = str(donnees.get("question", "")).strip()[:1000]
    if not question:
        return jsonify(texte="Posez une question sur un médicament ou un terme médical.")
    historique = [{"role": m["role"], "content": str(m["content"])[:6000]}
                  for m in (donnees.get("historique") or [])[-8:]
                  if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")]
    return jsonify(services.discuter(question, historique))
