"""PillPilot: API og hjemmeside i samme app.

Start: uv run --env-file .env python -m flask --app app run --debug --with-threads --port 5000
Hjemmeside: /login. Swagger: /docs. Der ændres ingen tabeller ved opstart.
"""

import logging
import os
from datetime import timedelta
from functools import wraps
from pathlib import Path

import psycopg
import requests
from apiflask import APIFlask, Schema, abort
from apiflask.fields import Email, Integer, String
from apiflask.validators import Length, Range
from cachelib.file import FileSystemCache
from flask import flash, redirect, render_template, request, session, url_for
from flask_session import Session
from flask_wtf.csrf import CSRFError, CSRFProtect

from auth import auth, check_login, create_token
from api.borger_api import api as borger_api
from api.kontaktperson_api import KontaktpersonOut, api as kontaktperson_api
from api.medicinplan_api import api as medicinplan_api
from api.medicinudlevering_api import api as medicinudlevering_api
from api.pilledispenser_api import api as pilledispenser_api
from api.udleveringsstatus_api import api as udleveringsstatus_api
from password_validation import (
    PASSWORD_ERROR,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_PATTERN,
    validate_password,
)

logger = logging.getLogger(__name__)


# App og indstillinger
app = APIFlask(__name__, title="PillPilot API")
app.json.ensure_ascii = False
app.secret_key = os.environ.get("JWT_SECRET_KEY", "")
if len(app.secret_key) < 32:
    raise RuntimeError("Sæt JWT_SECRET_KEY i .env til en tilfældig værdi på mindst 32 tegn.")

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000/api").rstrip("/")

# Sessionen gemmes på serveren. Browserens cookie indeholder kun et sessions-id.
session_dir = Path(app.instance_path) / "sessions"
session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
app.config.update(
    SESSION_TYPE="cachelib",
    SESSION_CACHELIB=FileSystemCache(cache_dir=str(session_dir), threshold=500),
    SESSION_PERMANENT=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_NAME="pillpilot_web_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("WEB_COOKIE_SECURE", "false").lower() == "true",
    SESSION_REFRESH_EACH_REQUEST=False,
    WTF_CSRF_CHECK_DEFAULT=False,
)
Session(app)
csrf = CSRFProtect(app)


@app.before_request
def protect_web_forms():
    """Kontrollér webformularer. API-kald bruger deres bearer-token."""
    if request.endpoint and not request.path.startswith("/api/"):
        csrf.protect()

def is_logged_in():
    return session.get("logged_in") is True and bool(session.get("token"))


def login_required(route_function):
    """Kontrollér tokenet og opdatér profilfelterne før en beskyttet side."""
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("login"))

        try:
            response = requests.get(
                f"{API_BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {session['token']}"},
                timeout=5,
                allow_redirects=False,
            )
        except requests.RequestException:
            return render_template("error.html", message="Kan ikke kontakte API'en. Prøv igen om lidt."), 503

        if response.status_code == 401:
            session.clear()
            flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
            return redirect(url_for("login"))
        if response.status_code != 200:
            return render_template("error.html", message="API'en kunne ikke hente dine oplysninger. Prøv igen om lidt."), 502

        try:
            data = response.json()
        except ValueError:
            data = None
        required_fields = {"kontaktperson_id", "fornavn", "efternavn", "email", "telefon", "aktiv"}
        if not isinstance(data, dict) or not required_fields.issubset(data) or data["aktiv"] is not True:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

        session["kontaktperson_id"] = data["kontaktperson_id"]
        session["fornavn"] = data["fornavn"]
        session["efternavn"] = data["efternavn"]
        session["email"] = data["email"]
        session["telefon"] = data["telefon"]
        session["aktiv"] = data["aktiv"]

        return route_function(*args, **kwargs)

    return wrapper


# API setup
app.register_blueprint(kontaktperson_api)
app.register_blueprint(borger_api)
app.register_blueprint(medicinplan_api)
app.register_blueprint(medicinudlevering_api)
app.register_blueprint(pilledispenser_api)
app.register_blueprint(udleveringsstatus_api)


class LoginIn(Schema):
    """Angiv password og enten email eller kontaktperson_id, ikke begge."""
    email = Email(load_default=None, allow_none=True, validate=Length(max=250))
    kontaktperson_id = Integer(load_default=None, allow_none=True, validate=Range(min=1))
    password = String(required=True, validate=Length(min=1, max=PASSWORD_MAX_LENGTH), load_only=True)


class TokenOut(Schema):
    """Tokenet kopieres til Authorize i Swagger uden at tilføje Bearer."""
    token = String()


@app.post("/api/auth/login")
@app.input(LoginIn)
@app.output(TokenOut)
def api_login(json_data: dict) -> dict:
    """Log ind med email eller id og få et bearer token."""
    if (json_data["email"] is None) == (json_data["kontaktperson_id"] is None):
        abort(400, "Angiv enten email eller kontaktperson_id, ikke begge")
    user = check_login(json_data["password"], json_data["email"], json_data["kontaktperson_id"])
    if user is None:
        abort(401, "Forkert login eller inaktiv kontaktperson")
    return {"token": create_token(user["kontaktperson_id"])}


@app.get("/api/auth/me")
@app.auth_required(auth)
@app.output(KontaktpersonOut)
def me() -> dict:
    """Vis den indloggede kontaktpersons oplysninger."""
    return auth.current_user


# Web routes
@app.route("/")
@app.doc(hide=True)
def home():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@app.doc(hide=True)
def login():
    if is_logged_in():
        return redirect(url_for("dashboard"))

    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Udfyld både email og adgangskode.", "warning")
            return render_template("login.html", email=email)
        if len(email) > 250 or len(password) > PASSWORD_MAX_LENGTH:
            flash("Email eller adgangskode er for lang.", "warning")
            return render_template("login.html", email=email)

        try:
            # 1. Log ind hos API'en og få et token.
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=5,
                allow_redirects=False,
            )

            if response.status_code == 401:
                flash("Forkert email/adgangskode, eller kontaktpersonen er inaktiv.", "danger")
                return render_template("login.html", email=email)
            if response.status_code in (400, 422):
                flash("Kontrollér at email og adgangskode er udfyldt korrekt.", "warning")
                return render_template("login.html", email=email)
            if response.status_code != 200:
                flash("API'en kunne ikke gennemføre login. Prøv igen om lidt.", "danger")
                return render_template("login.html", email=email)

            token_data = response.json()
            token = token_data.get("token") if isinstance(token_data, dict) else None
            if not isinstance(token, str) or not token.strip():
                flash("API'en returnerede ikke et gyldigt login-svar.", "danger")
                return render_template("login.html", email=email)

            # 2. Hent kontaktpersonens oplysninger med det nye token.
            response = requests.get(
                f"{API_BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
                allow_redirects=False,
            )
            if response.status_code == 401:
                flash("Dit login er ikke længere gyldigt. Prøv at logge ind igen.", "warning")
                return render_template("login.html", email=email)
            if response.status_code != 200:
                flash("API'en kunne ikke hente kontaktpersonen. Prøv igen om lidt.", "danger")
                return render_template("login.html", email=email)

            data = response.json()
            required_fields = {"kontaktperson_id", "fornavn", "efternavn", "email", "telefon", "aktiv"}
            if not isinstance(data, dict) or not required_fields.issubset(data) or data["aktiv"] is not True:
                flash("API'en gav et uventet svar. Prøv igen om lidt.", "danger")
                return render_template("login.html", email=email)

            # 3. Gem login og profilfelter
            session.clear()
            session["logged_in"] = True
            session["token"] = token
            session["kontaktperson_id"] = data["kontaktperson_id"]
            session["fornavn"] = data["fornavn"]
            session["efternavn"] = data["efternavn"]
            session["email"] = data["email"]
            session["telefon"] = data["telefon"]
            session["aktiv"] = data["aktiv"]
            app.session_interface.regenerate(session)

            return redirect(url_for("dashboard"))

        except ValueError:
            flash("API'en gav et uventet svar. Prøv igen om lidt.", "danger")
        except requests.RequestException:
            flash("Kan ikke kontakte API'en. Kontrollér API_BASE_URL i .env.", "danger")

    return render_template("login.html", email=email)


@app.route("/dashboard")
@app.doc(hide=True)
@login_required
def dashboard():
    try:
        response = requests.get(
            f"{API_BASE_URL}/borger",
            headers={"Authorization": f"Bearer {session['token']}"},
            params={"kontaktperson_id": session["kontaktperson_id"]},
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        return render_template("error.html", message="Kan ikke kontakte API'en. Prøv igen om lidt."), 503

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code != 200:
        return render_template("error.html", message="Kunne ikke hente dine borgere. Prøv igen om lidt."), 502

    try:
        borgere = response.json()
    except ValueError:
        return render_template("error.html", message="API'en gav et ugyldigt svar. Prøv igen om lidt."), 502
    if not isinstance(borgere, list):
        return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

    return render_template(
        "dashboard.html",
        borgere=borgere,
        password_pattern=PASSWORD_PATTERN,
        password_error=PASSWORD_ERROR,
        password_min_length=PASSWORD_MIN_LENGTH,
        password_max_length=PASSWORD_MAX_LENGTH,
        password_settings_open=request.args.get("settings") == "password",
    )


@app.route("/settings/password", methods=["POST"])
@app.doc(hide=True)
@login_required
def update_password():
    """Skift den indloggede kontaktpersons password gennem API'et."""
    password = request.form.get("password", "")
    try:
        validate_password(password)
    except ValueError as error:
        flash(str(error), "warning")
        return redirect(url_for("dashboard", settings="password"))

    try:
        response = requests.patch(
            f"{API_BASE_URL}/kontaktperson/{session['kontaktperson_id']}/password",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={"password": password},
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Prøv igen om lidt.", "danger")
        return redirect(url_for("dashboard", settings="password"))

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code in (400, 422):
        flash(PASSWORD_ERROR, "warning")
        return redirect(url_for("dashboard", settings="password"))
    if response.status_code != 200:
        flash("Adgangskoden kunne ikke opdateres. Prøv igen om lidt.", "danger")
        return redirect(url_for("dashboard", settings="password"))

    flash("Din adgangskode er opdateret.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout", methods=["POST"])
@app.doc(hide=True)
def logout():
    app.session_interface.regenerate(session)
    session.clear()
    flash("Du er logget ud.", "success")
    return redirect(url_for("login"))


# Fejlhåndtering
@app.errorhandler(CSRFError)
def csrf_error(error):
    return render_template(
        "error.html", message="Formularen er udløbet eller ugyldig. Åbn siden igen og prøv på ny."
    ), 400


@app.errorhandler(psycopg.errors.UniqueViolation)
def duplicate_error(error) -> tuple[dict, int]:
    """Forklar en UNIQUE-fejl uden at udlevere SQL eller personoplysninger."""
    return {"message": "Værdien findes allerede. Kontrollér email, enheds-id, borger eller planlagt tid.",
            "constraint": error.diag.constraint_name}, 409


@app.errorhandler(psycopg.errors.ForeignKeyViolation)
def relation_error(error) -> tuple[dict, int]:
    """Forklar ugyldige relationer og sletninger, som databasen blokerer."""
    return {"message": "Et tilknyttet id findes ikke, eller rækken bruges af andre registreringer.",
            "constraint": error.diag.constraint_name}, 409


@app.errorhandler(psycopg.errors.CheckViolation)
def check_error(error) -> tuple[dict, int]:
    """Vis navnet på den CHECK-regel, som requestet bryder."""
    return {"message": "Værdierne bryder en regel i databasen.",
            "constraint": error.diag.constraint_name}, 400


@app.errorhandler(ValueError)
def value_error(error: ValueError) -> tuple[dict, int]:
    """Vis de forklaringer, som databasefunktionernes egne kontroller giver."""
    return {"message": str(error)}, 400


@app.errorhandler(psycopg.Error)
def database_error(error: psycopg.Error) -> tuple[dict, int]:
    """Send aldrig PostgreSQLs rå fejlbesked til klienten."""
    logger.error("Databasefejl af typen %s", type(error).__name__)
    return {"message": "Databasefejl. Kontrollér forbindelsen og serverens log."}, 500


@app.after_request
def no_cache(response):
    """Bed klienter om ikke at gemme personoplysninger fra API-svar i cache."""
    response.headers["Cache-Control"] = "no-store"
    return response

