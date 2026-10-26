"""Pages publiques."""

from flask import Blueprint, render_template

from .services import statistiques_referentiels

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html", stats=statistiques_referentiels())
