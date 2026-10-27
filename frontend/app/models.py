"""Modèles : utilisateurs et documents numérisés."""

import json
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager

ROLES = {
    "patient": "Patient",
    "medecin": "Médecin",
    "pharmacien": "Pharmacien",
    "assurance": "Assurance / mutuelle",
    "etablissement": "Établissement de santé",
}

TYPES_DOCUMENT = {
    "ordonnance": "Ordonnance",
    "bulletin": "Bulletin de soins",
}


def maintenant():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prenom = db.Column(db.String(80), nullable=False)
    nom = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    telephone = db.Column(db.String(20))
    role = db.Column(db.String(20), nullable=False, default="patient")
    organisation = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)
    # Compte démo partagé : rien n'est enregistré (ni document ni image), voir outils.extraction.
    demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=maintenant)
    documents = db.relationship("Document", backref="user", cascade="all, delete-orphan",
                                order_by="Document.created_at.desc()")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_label(self):
        return ROLES.get(self.role, self.role)

    @property
    def initiales(self):
        return (self.prenom[:1] + self.nom[:1]).upper()


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True, nullable=False)
    type = db.Column(db.String(20), nullable=False, default="ordonnance")
    image = db.Column(db.String(120), nullable=False)  # nom du fichier dans instance/uploads/
    medecin = db.Column(db.String(200))
    texte = db.Column(db.Text, default="")
    numero = db.Column(db.String(50))  # numéro du bulletin de soins
    date_document = db.Column(db.String(20))  # date lue sur l'ordonnance (jj/mm/aaaa)
    modele = db.Column(db.String(120))  # modèle de lecture utilisé par le backend
    demo = db.Column(db.Boolean, default=False)  # texte d'exemple (lecture pas encore disponible)
    # Zones détectées par le backend, en fractions de l'image : [{"libelle", "x", "y", "l", "h"}]
    boites = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=maintenant)

    @property
    def type_label(self):
        return TYPES_DOCUMENT.get(self.type, self.type)

    @property
    def zones(self):
        try:
            return json.loads(self.boites or "[]")
        except ValueError:
            return []

    @property
    def lignes(self):
        return [l for l in (self.texte or "").splitlines() if l.strip()]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
