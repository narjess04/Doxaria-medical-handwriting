"""Formulaires d'inscription et de connexion (protégés contre le CSRF)."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, SelectField, StringField, TelField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError

from .models import ROLES, User


def nettoie_email(valeur):
    """Espaces et majuscules ajoutés par l'autocomplétion des téléphones."""
    return valeur.strip().lower() if valeur else valeur


class RegisterForm(FlaskForm):
    prenom = StringField("Prénom", validators=[DataRequired("Indiquez votre prénom."), Length(max=80)])
    nom = StringField("Nom", validators=[DataRequired("Indiquez votre nom."), Length(max=80)])
    email = EmailField("Adresse e-mail", filters=[nettoie_email], validators=[
        DataRequired("Indiquez votre adresse e-mail."),
        Email("Adresse e-mail invalide."),
        Length(max=255),
    ])
    telephone = TelField("Téléphone (facultatif)", validators=[
        Optional(), Regexp(r"^\+?[\d\s.-]{8,20}$", message="Numéro de téléphone invalide."),
    ])
    role = SelectField("Vous êtes", choices=list(ROLES.items()))
    organisation = StringField("Organisation (facultatif)", validators=[Optional(), Length(max=120)])
    password = PasswordField("Mot de passe", validators=[
        DataRequired("Choisissez un mot de passe."),
        Length(min=8, message="Au moins 8 caractères."),
        Regexp(r"^(?=.*[A-Za-z])(?=.*\d)", message="Au moins une lettre et un chiffre."),
    ])
    confirm = PasswordField("Confirmer le mot de passe", validators=[
        DataRequired("Confirmez le mot de passe."),
        EqualTo("password", "Les mots de passe ne correspondent pas."),
    ])
    accept = BooleanField("J'accepte que mes documents soient traités pour leur numérisation.",
                          validators=[DataRequired("Vous devez accepter pour créer un compte.")])

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("Un compte existe déjà avec cette adresse.")


class LoginForm(FlaskForm):
    email = EmailField("Adresse e-mail", filters=[nettoie_email],
                       validators=[DataRequired("Indiquez votre adresse e-mail."), Email("Adresse e-mail invalide.")])
    password = PasswordField("Mot de passe", validators=[DataRequired("Indiquez votre mot de passe.")])
    remember = BooleanField("Rester connecté")
