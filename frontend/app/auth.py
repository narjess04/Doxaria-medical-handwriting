"""Inscription, connexion et déconnexion."""

import secrets
from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import db
from .forms import LoginForm, RegisterForm
from .models import User

bp = Blueprint("auth", __name__)


def page_suivante():
    """Page demandée avant la connexion, si elle appartient au site."""
    cible = request.args.get("next", "")
    if cible.startswith("/") and not cible.startswith("//") and not urlsplit(cible).netloc:
        return cible
    return url_for("outils.dashboard")


@bp.route("/inscription", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("outils.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            prenom=form.prenom.data.strip(),
            nom=form.nom.data.strip(),
            email=form.email.data.strip().lower(),
            telephone=(form.telephone.data or "").strip() or None,
            role=form.role.data,
            organisation=(form.organisation.data or "").strip() or None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Bienvenue {user.prenom}, votre compte est créé.", "success")
        return redirect(url_for("outils.dashboard"))
    return render_template("auth/register.html", form=form)


DEMO_EMAIL = "demo@meditrust.tn"


@bp.route("/demo", methods=["POST"])
def demo():
    """Connexion au compte démo partagé, sans mot de passe. Ce compte ne conserve rien :
    les documents analysés sont affichés une fois, puis oubliés avec leur image."""
    user = User.query.filter_by(email=DEMO_EMAIL).first()
    if user is None:
        user = User(prenom="Démo", nom="MediTrust", email=DEMO_EMAIL, role="patient", demo=True)
        user.set_password(secrets.token_urlsafe(32))  # mot de passe inconnu : connexion par ce bouton seulement
        db.session.add(user)
    # Par sécurité : aucun document ne doit rester attaché au compte démo.
    for doc in list(user.documents):
        db.session.delete(doc)
    db.session.commit()
    logout_user()
    login_user(user, remember=False)
    flash("Compte démo : testez librement, aucune ordonnance ni image n'est conservée.", "info")
    return redirect(url_for("outils.extraction"))


@bp.route("/connexion", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("outils.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(page_suivante())
        # Même message que l'adresse existe ou non.
        flash("Adresse e-mail ou mot de passe incorrect.", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/deconnexion", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("main.index"))
