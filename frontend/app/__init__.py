"""Application Flask MediTrust : pages publiques, authentification, espace utilisateur."""

import os
from datetime import timedelta, timezone
from pathlib import Path

from flask import Flask, flash, redirect, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect, text

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

HEURE_TUNISIE = timezone(timedelta(hours=1), "Africa/Tunis")


def create_app(config=Config):
    # Sur Vercel, seul /tmp est inscriptible : les images n'y passent que le temps de l'analyse.
    instance = Path("/tmp/instance") if os.environ.get("VERCEL") else Path(__file__).resolve().parent.parent / "instance"
    app = Flask(__name__, instance_path=str(instance))
    app.config.from_object(config)
    Path(app.instance_path).mkdir(exist_ok=True)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{Path(app.instance_path) / 'meditrust.db'}"

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Connectez-vous pour accéder à cette page."
    login_manager.login_message_category = "info"

    from . import models  # noqa: F401  (enregistre le chargeur d'utilisateur)
    from .auth import bp as auth_bp
    from .main import bp as main_bp
    from .outils import bp as outils_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(outils_bp)

    @app.template_global()
    def asset(fichier):
        """URL d'un fichier statique, versionnée par sa date de modification (cache navigateur)."""
        chemin = Path(app.static_folder) / fichier
        return url_for("static", filename=fichier, v=int(chemin.stat().st_mtime) if chemin.exists() else 0)

    @app.template_filter("date_locale")
    def date_locale(d, fmt="%d/%m/%Y à %H:%M"):
        # Les dates sont enregistrées en UTC (SQLite les relit sans fuseau) ; la Tunisie est en UTC+1 toute l'année.
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(HEURE_TUNISIE).strftime(fmt)

    @app.errorhandler(413)
    def fichier_trop_gros(_):
        flash(f"Fichier trop volumineux (maximum {app.config['MAX_CONTENT_LENGTH'] // 2**20} Mo).", "error")
        return redirect(request.referrer or "/")

    with app.app_context():
        db.create_all()
        ajoute_colonnes_manquantes()
    return app


def ajoute_colonnes_manquantes():
    """Migration minimale : ajoute aux tables existantes les colonnes ajoutées au modèle
    depuis (create_all ne modifie pas une table existante). Les données sont conservées."""
    inspecteur = inspect(db.engine)
    for table in db.metadata.sorted_tables:
        existantes = {c["name"] for c in inspecteur.get_columns(table.name)}
        for colonne in table.columns:
            if colonne.name not in existantes:
                type_sql = colonne.type.compile(db.engine.dialect)
                defaut = colonne.default.arg if colonne.default is not None and not callable(colonne.default.arg) else None
                clause = f" DEFAULT '{defaut}'" if isinstance(defaut, str) else ""
                with db.engine.begin() as cnx:
                    cnx.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{colonne.name}" {type_sql}{clause}'))
