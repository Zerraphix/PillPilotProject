"""PillPilot: API og hjemmeside i samme app.

Start: uv run --env-file .env python -m flask --app app run --debug --with-threads --port 5000
Hjemmeside: /login. Swagger: /docs. Der ændres ingen tabeller ved opstart.
"""

import logging
import os
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

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


@app.template_filter("date_da")
def format_date(value):
    """Vis en ISO-dato som dag-måned-år."""
    if not value:
        return "Ikke angivet"
    try:
        return date.fromisoformat(value).strftime("%d-%m-%Y")
    except (TypeError, ValueError):
        return str(value)


@app.template_filter("datetime_da")
def format_datetime(value):
    """Vis et ISO-tidspunkt i dansk tid, når API'et angiver en tidszone."""
    if not value:
        return "Ikke angivet"
    try:
        timestamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return str(value)
    if timestamp.tzinfo is not None:
        return timestamp.astimezone(ZoneInfo("Europe/Copenhagen")).strftime("%d-%m-%Y kl. %H:%M:%S") + " (dansk tid)"
    return timestamp.strftime("%d-%m-%Y kl. %H:%M:%S") + " (tidszone ikke angivet)"


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
    """Vis egne borgere med dispenser, plan og kommende udlevering."""
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

    borgeroversigter = []
    nu = datetime.now(ZoneInfo("Europe/Copenhagen"))
    for borger in borgere:
        if not isinstance(borger, dict) or type(borger.get("borger_id")) is not int or borger["borger_id"] < 1:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
        if borger.get("kontaktperson_id") != session["kontaktperson_id"]:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
        borger_id = borger["borger_id"]

        try:
            oversigt_response = requests.get(
                f"{API_BASE_URL}/borger/{borger_id}/oversigt",
                headers={"Authorization": f"Bearer {session['token']}"},
                timeout=5,
                allow_redirects=False,
            )
            antal_response = requests.get(
                f"{API_BASE_URL}/pilledispenser/leveringer-tilbage",
                headers={"Authorization": f"Bearer {session['token']}"},
                params={"borger_id": borger_id},
                timeout=5,
                allow_redirects=False,
            )
        except requests.RequestException:
            return render_template("error.html", message="Kan ikke kontakte API'en. Prøv igen om lidt."), 503

        if 401 in (oversigt_response.status_code, antal_response.status_code):
            session.clear()
            flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
            return redirect(url_for("login"))
        if oversigt_response.status_code != 200 or antal_response.status_code != 200:
            return render_template("error.html", message="Kunne ikke hente borgernes overblik. Prøv igen om lidt."), 502

        try:
            oversigt = oversigt_response.json()
            antal_resultater = antal_response.json()
        except ValueError:
            return render_template("error.html", message="API'en gav et ugyldigt svar. Prøv igen om lidt."), 502
        required_fields = {"borger", "pilledispensere", "medicinplaner", "medicinudleveringer"}
        if not isinstance(oversigt, dict) or not required_fields.issubset(oversigt):
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

        borger = oversigt["borger"]
        pilledispensere = oversigt["pilledispensere"]
        medicinplaner = oversigt["medicinplaner"]
        udleveringer = oversigt["medicinudleveringer"]
        required_fields = {"borger_id", "kontaktperson_id", "fornavn", "efternavn", "aktiv"}
        if not isinstance(borger, dict) or not required_fields.issubset(borger) or borger["borger_id"] != borger_id:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
        if borger["kontaktperson_id"] != session["kontaktperson_id"]:
            return render_template("error.html", message="Borgerens kontaktperson er ændret. Opdater dashboardet."), 502
        for liste in (pilledispensere, medicinplaner, udleveringer, antal_resultater):
            if not isinstance(liste, list):
                return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
        if len(pilledispensere) > 1 or len(antal_resultater) > 1:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

        pilledispenser = pilledispensere[0] if pilledispensere else None
        if pilledispenser is not None:
            required_fields = {"pilledispenser_id", "borger_id", "enhed_id", "aktiv"}
            if not isinstance(pilledispenser, dict) or not required_fields.issubset(pilledispenser) or pilledispenser["borger_id"] != borger_id:
                return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

        medicinplan = None
        for plan in medicinplaner:
            required_fields = {"medicinplan_id", "borger_id", "navn", "aktiv"}
            if not isinstance(plan, dict) or not required_fields.issubset(plan) or plan["borger_id"] != borger_id:
                return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
            if plan["aktiv"]:
                medicinplan = plan
        if medicinplan is None and medicinplaner:
            medicinplan = medicinplaner[-1]

        naeste_udlevering = None
        tidspunkt_passeret = False
        for udlevering in reversed(udleveringer):
            required_fields = {"medicinplan_id", "pilledispenser_id", "borger_id", "status_kode", "planlagt_tid"}
            if not isinstance(udlevering, dict) or not required_fields.issubset(udlevering) or udlevering["borger_id"] != borger_id:
                return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
            if pilledispenser and udlevering["pilledispenser_id"] == pilledispenser["pilledispenser_id"] and udlevering["status_kode"] == "planlagt":
                naeste_udlevering = udlevering
                break

        if naeste_udlevering:
            medicinplan = None
            for plan in medicinplaner:
                if plan["medicinplan_id"] == naeste_udlevering["medicinplan_id"]:
                    medicinplan = plan
                    break
            if medicinplan is None:
                return render_template("error.html", message="Kunne ikke finde planen for næste udlevering. Opdater dashboardet."), 502
            try:
                planlagt_tid = datetime.fromisoformat(naeste_udlevering["planlagt_tid"])
            except (TypeError, ValueError):
                return render_template("error.html", message="API'en gav et ugyldigt tidspunkt. Prøv igen om lidt."), 502
            if planlagt_tid.tzinfo is None:
                return render_template("error.html", message="API'ets udlevering mangler en tidszone. Prøv igen om lidt."), 502
            tidspunkt_passeret = planlagt_tid < nu

        leveringer_tilbage = None
        if antal_resultater:
            antal = antal_resultater[0]
            required_fields = {"borger_id", "pilledispenser_id", "planlagte_tilbage"}
            if not isinstance(antal, dict) or not required_fields.issubset(antal) or antal["borger_id"] != borger_id:
                return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
            if type(antal["planlagte_tilbage"]) is not int or antal["planlagte_tilbage"] < 0:
                return render_template("error.html", message="API'en gav et ugyldigt antal udleveringer. Prøv igen om lidt."), 502
            if not pilledispenser or antal["pilledispenser_id"] != pilledispenser["pilledispenser_id"]:
                return render_template("error.html", message="Borgerens dispenser er ændret. Opdater dashboardet."), 502
            if pilledispenser["aktiv"]:
                leveringer_tilbage = antal["planlagte_tilbage"]

        borgeroversigter.append({
            "borger": borger,
            "pilledispenser": pilledispenser,
            "medicinplan": medicinplan,
            "naeste_udlevering": naeste_udlevering,
            "tidspunkt_passeret": tidspunkt_passeret,
            "leveringer_tilbage": leveringer_tilbage,
        })

    return render_template(
        "dashboard.html",
        borgeroversigter=borgeroversigter,
        password_pattern=PASSWORD_PATTERN,
        password_error=PASSWORD_ERROR,
        password_min_length=PASSWORD_MIN_LENGTH,
        password_max_length=PASSWORD_MAX_LENGTH,
        password_settings_open=request.args.get("settings") == "password",
    )


# Borger routes
@app.route("/borgere")
@app.doc(hide=True)
@login_required
def borgere():
    """Vis alle borgere og kontaktpersoner samt formularen til oprettelse."""
    try:
        borger_response = requests.get(
            f"{API_BASE_URL}/borger",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
        kontaktperson_response = requests.get(
            f"{API_BASE_URL}/kontaktperson",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        return render_template("error.html", message="Kan ikke kontakte API'en. Prøv igen om lidt."), 503

    if 401 in (borger_response.status_code, kontaktperson_response.status_code):
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if borger_response.status_code != 200 or kontaktperson_response.status_code != 200:
        return render_template("error.html", message="Kunne ikke hente borgere og kontaktpersoner. Prøv igen om lidt."), 502

    try:
        alle_borgere = borger_response.json()
        kontaktpersoner = kontaktperson_response.json()
    except ValueError:
        return render_template("error.html", message="API'en gav et ugyldigt svar. Prøv igen om lidt."), 502
    if not isinstance(alle_borgere, list) or not isinstance(kontaktpersoner, list):
        return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

    return render_template(
        "borgere.html",
        borgere=alle_borgere,
        kontaktpersoner=kontaktpersoner,
    )


@app.route("/borgere/create", methods=["POST"])
@app.doc(hide=True)
@login_required
def create_borger():
    """Opret borgeren gennem API'et med den valgte kontaktperson."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/borger",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={
                "kontaktperson_id": request.form.get("kontaktperson_id", type=int),
                "fornavn": request.form.get("fornavn", "").strip(),
                "efternavn": request.form.get("efternavn", "").strip(),
                "birthday": request.form.get("birthday", ""),
                "telefon": request.form.get("telefon", "").strip() or None,
                "adresse": request.form.get("adresse", "").strip() or None,
                "diagnose": request.form.get("diagnose", "").strip() or None,
                "allergi": request.form.get("allergi", "").strip() or None,
            },
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Kontrollér oversigten, før du prøver igen.", "danger")
        return redirect(url_for("borgere"))

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 201:
        flash("Borgeren er oprettet og tilknyttet den valgte kontaktperson.", "success")
    elif response.status_code == 409:
        flash("Den valgte kontaktperson findes ikke længere. Vælg en kontaktperson fra listen.", "warning")
    elif response.status_code in (400, 422):
        flash("Kontrollér formularens felter. Fornavn, efternavn, fødselsdato og kontaktperson skal være udfyldt korrekt.", "warning")
    else:
        flash("Borgeren kunne ikke oprettes. Prøv igen om lidt.", "danger")

    return redirect(url_for("borgere"))


@app.route("/borger/<int:borger_id>")
@app.doc(hide=True)
@login_required
def borger_view(borger_id):
    """Vis borgerens oplysninger, medicinplan og udleveringer."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/borger/{borger_id}/oversigt",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
        kontaktperson_response = requests.get(
            f"{API_BASE_URL}/kontaktperson",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        return render_template("error.html", message="Kan ikke kontakte API'en. Prøv igen om lidt."), 503

    if 401 in (response.status_code, kontaktperson_response.status_code):
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 404:
        return render_template("error.html", message="Borgeren findes ikke."), 404
    if response.status_code != 200:
        return render_template("error.html", message="Kunne ikke hente borgerens oversigt. Prøv igen om lidt."), 502
    if kontaktperson_response.status_code != 200:
        return render_template("error.html", message="Kunne ikke hente kontaktpersoner. Prøv igen om lidt."), 502
    try:
        oversigt = response.json()
        kontaktpersoner = kontaktperson_response.json()
    except ValueError:
        return render_template("error.html", message="API'en gav et ugyldigt svar. Prøv igen om lidt."), 502
    required_fields = {"borger", "pilledispensere", "medicinplaner", "medicinudleveringer"}
    if not isinstance(oversigt, dict) or not required_fields.issubset(oversigt):
        return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

    borger = oversigt["borger"]
    pilledispensere = oversigt["pilledispensere"]
    medicinplaner = oversigt["medicinplaner"]
    udleveringer = oversigt["medicinudleveringer"]
    required_fields = {"borger_id", "fornavn", "efternavn", "aktiv"}
    if not isinstance(borger, dict) or not required_fields.issubset(borger) or borger["borger_id"] != borger_id:
        return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
    for liste in (kontaktpersoner, pilledispensere, medicinplaner, udleveringer):
        if not isinstance(liste, list):
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

    if len(pilledispensere) > 1:
        return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
    pilledispenser = pilledispensere[0] if pilledispensere else None
    if pilledispenser is not None:
        required_fields = {"pilledispenser_id", "borger_id", "antal_rum", "aktiv"}
        if not isinstance(pilledispenser, dict) or not required_fields.issubset(pilledispenser) or pilledispenser["borger_id"] != borger_id:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
        if type(pilledispenser["antal_rum"]) is not int or pilledispenser["antal_rum"] < 1:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

    edit_medicinplan_id = request.args.get("edit_medicinplan_id", type=int)
    medicinplan_id = request.args.get("medicinplan_id", type=int)
    if edit_medicinplan_id is not None:
        medicinplan_id = edit_medicinplan_id

    medicinplan = None
    for plan in medicinplaner:
        required_fields = {"medicinplan_id", "navn", "tidspunkt", "startdato", "aktiv"}
        if not isinstance(plan, dict) or not required_fields.issubset(plan) or plan.get("borger_id") != borger_id:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
        if medicinplan_id is not None and plan.get("medicinplan_id") == medicinplan_id:
            medicinplan = plan

    if medicinplan_id is not None and medicinplan is None:
        flash("Medicinplanen findes ikke på denne borger.", "warning")
        return redirect(url_for("borger_view", borger_id=borger_id))

    if medicinplan is None:
        for plan in reversed(medicinplaner):
            if plan.get("aktiv"):
                medicinplan = plan
                break
        if medicinplan is None and medicinplaner:
            medicinplan = medicinplaner[-1]

    medicinudleveringer = []
    aabne_udleveringer = []
    for udlevering in reversed(udleveringer):
        required_fields = {"udlevering_id", "medicinplan_id", "pilledispenser_id", "status_kode", "planlagt_tid", "afhentningsfrist"}
        if not isinstance(udlevering, dict) or not required_fields.issubset(udlevering) or udlevering.get("borger_id") != borger_id:
            return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502
        if medicinplan and udlevering["medicinplan_id"] == medicinplan["medicinplan_id"]:
            medicinudleveringer.append(udlevering)
        if pilledispenser and udlevering["pilledispenser_id"] == pilledispenser["pilledispenser_id"]:
            if udlevering["status_kode"] in ("planlagt", "udleveret", "ikke_afhentet"):
                aabne_udleveringer.append(udlevering)

    fyldning_blokering = None
    if not medicinplan:
        fyldning_blokering = "Opret en medicinplan, før du planlægger udleveringer."
    elif borger["aktiv"] is not True:
        fyldning_blokering = "Borgeren skal være aktiv, før du kan oprette udleveringer."
    elif medicinplan["aktiv"] is not True:
        fyldning_blokering = "Medicinplanen skal være aktiv, før du kan oprette udleveringer."
    elif not pilledispenser:
        fyldning_blokering = "Borgeren skal have en pilledispenser, før du kan oprette udleveringer."
    elif pilledispenser["aktiv"] is not True:
        fyldning_blokering = "Pilledispenseren skal være aktiv, før du kan oprette udleveringer."
    elif aabne_udleveringer:
        fyldning_blokering = "Dispenseren har stadig åbne udleveringer. De skal være afsluttet, før du kan oprette en ny fyldning."

    return render_template(
        "borger.html",
        borger=borger,
        kontaktpersoner=kontaktpersoner,
        borger_settings_open=request.args.get("settings") == "borger",
        medicinplaner=medicinplaner,
        medicinplan=medicinplan,
        edit_medicinplan=medicinplan if edit_medicinplan_id is not None else None,
        pilledispenser=pilledispenser,
        medicinudleveringer=medicinudleveringer,
        aabne_udleveringer=aabne_udleveringer,
        fyldning_blokering=fyldning_blokering,
        fyldning_form_open=request.args.get("opret_udleveringer") == "1",
    )


@app.route("/borger/<int:borger_id>/update", methods=["POST"])
@app.doc(hide=True)
@login_required
def update_borger(borger_id):
    """Gem borgerens oplysninger gennem API'et."""
    settings_url = url_for("borger_view", borger_id=borger_id, settings="borger")

    try:
        response = requests.put(
            f"{API_BASE_URL}/borger/{borger_id}",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={
                "kontaktperson_id": request.form.get("kontaktperson_id", type=int),
                "fornavn": request.form.get("fornavn", "").strip(),
                "efternavn": request.form.get("efternavn", "").strip(),
                "birthday": request.form.get("birthday", ""),
                "telefon": request.form.get("telefon", "").strip() or None,
                "adresse": request.form.get("adresse", "").strip() or None,
                "diagnose": request.form.get("diagnose", "").strip() or None,
                "allergi": request.form.get("allergi", "").strip() or None,
                "aktiv": request.form.get("aktiv") == "true",
            },
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Kontrollér oplysningerne, før du prøver igen.", "danger")
        return redirect(settings_url)

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 200:
        flash("Borgerens oplysninger er opdateret.", "success")
        return redirect(url_for("borger_view", borger_id=borger_id))
    if response.status_code == 404:
        flash("Borgeren findes ikke længere.", "warning")
        return redirect(url_for("borgere"))
    if response.status_code == 409:
        flash("Den valgte kontaktperson findes ikke længere. Vælg en kontaktperson fra listen.", "warning")
    elif response.status_code in (400, 422):
        flash("Kontrollér formularens felter. Fornavn, efternavn, fødselsdato og kontaktperson skal være udfyldt korrekt.", "warning")
    else:
        flash("Borgerens oplysninger kunne ikke opdateres. Prøv igen om lidt.", "danger")

    return redirect(settings_url)


# Medicinplan routes
@app.route("/borger/<int:borger_id>/medicinplan/create", methods=["POST"])
@app.doc(hide=True)
@login_required
def create_medicinplan(borger_id):
    """Opret en medicinplan for den viste borger."""
    borger_url = url_for("borger_view", borger_id=borger_id)

    try:
        response = requests.post(
            f"{API_BASE_URL}/medicinplan",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={
                "borger_id": borger_id,
                "navn": request.form.get("navn", "").strip(),
                "tidspunkt": request.form.get("tidspunkt", ""),
                "startdato": request.form.get("startdato", ""),
                "slutdato": request.form.get("slutdato", "").strip() or None,
            },
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Kontrollér planerne, før du prøver igen.", "danger")
        return redirect(borger_url)

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 201:
        flash("Medicinplanen er oprettet.", "success")
    elif response.status_code in (400, 422):
        flash("Kontrollér navn, klokkeslæt og datoer. Slutdato må ikke være før startdato.", "warning")
    elif response.status_code == 409:
        flash("Borgeren eller opretteren kunne ikke findes. Opdater siden og prøv igen.", "warning")
    else:
        flash("Medicinplanen kunne ikke oprettes. Prøv igen om lidt.", "danger")

    return redirect(borger_url)


@app.route("/borger/<int:borger_id>/medicinplan/<int:medicinplan_id>/update", methods=["POST"])
@app.doc(hide=True)
@login_required
def update_medicinplan(borger_id, medicinplan_id):
    """Opdatér en af den viste borgers medicinplaner."""
    borger_url = url_for("borger_view", borger_id=borger_id)
    edit_url = url_for("borger_view", borger_id=borger_id, edit_medicinplan_id=medicinplan_id)

    # Kontrollér, at planen hører til borgeren på siden, før ændringerne sendes.
    try:
        response = requests.get(
            f"{API_BASE_URL}/medicinplan/{medicinplan_id}",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Prøv igen om lidt.", "danger")
        return redirect(edit_url)

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 404:
        flash("Medicinplanen findes ikke længere.", "warning")
        return redirect(borger_url)
    if response.status_code != 200:
        flash("Medicinplanen kunne ikke hentes. Prøv igen om lidt.", "danger")
        return redirect(edit_url)

    try:
        plan = response.json()
    except ValueError:
        flash("API'en gav et ugyldigt svar. Prøv igen om lidt.", "danger")
        return redirect(borger_url)
    if not isinstance(plan, dict) or plan.get("medicinplan_id") != medicinplan_id:
        flash("API'en gav et uventet svar. Prøv igen om lidt.", "danger")
        return redirect(borger_url)
    if plan.get("borger_id") != borger_id:
        flash("Medicinplanen hører ikke til denne borger.", "warning")
        return redirect(borger_url)

    try:
        response = requests.put(
            f"{API_BASE_URL}/medicinplan/{medicinplan_id}",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={
                "borger_id": borger_id,
                "navn": request.form.get("navn", "").strip(),
                "tidspunkt": request.form.get("tidspunkt", ""),
                "startdato": request.form.get("startdato", ""),
                "slutdato": request.form.get("slutdato", "").strip() or None,
                "aktiv": request.form.get("aktiv") == "true",
            },
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Kontrollér planen, før du prøver igen.", "danger")
        return redirect(edit_url)

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 200:
        flash("Medicinplanen er opdateret.", "success")
        return redirect(borger_url)
    if response.status_code == 404:
        flash("Medicinplanen findes ikke længere.", "warning")
        return redirect(borger_url)
    if response.status_code in (400, 422):
        flash("Kontrollér navn, klokkeslæt og datoer. Slutdato må ikke være før startdato.", "warning")
    elif response.status_code == 409:
        flash("Borgeren kunne ikke tilknyttes planen. Opdater siden og prøv igen.", "warning")
    else:
        flash("Medicinplanen kunne ikke opdateres. Prøv igen om lidt.", "danger")

    return redirect(edit_url)


# Udlevering routes
@app.route("/borger/<int:borger_id>/medicinplan/<int:medicinplan_id>/fyldning/create", methods=["POST"])
@app.doc(hide=True)
@login_required
def create_fyldning(borger_id, medicinplan_id):
    """Send de tre formularfelter til API'et, som opretter udleveringerne samlet."""
    borger_url = url_for("borger_view", borger_id=borger_id)
    plan_url = url_for("borger_view", borger_id=borger_id, medicinplan_id=medicinplan_id)
    form_url = url_for("borger_view", borger_id=borger_id, medicinplan_id=medicinplan_id, opret_udleveringer=1)

    # Kontrollér, at planen i URL'en hører til borgeren på siden.
    try:
        response = requests.get(
            f"{API_BASE_URL}/medicinplan/{medicinplan_id}",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kunne ikke hente medicinplanen. Prøv igen om lidt.", "danger")
        return redirect(form_url)

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 404:
        flash("Medicinplanen findes ikke længere.", "warning")
        return redirect(borger_url)
    if response.status_code != 200:
        flash("Kunne ikke hente medicinplanen. Prøv igen om lidt.", "danger")
        return redirect(form_url)
    try:
        plan = response.json()
    except ValueError:
        plan = None
    if not isinstance(plan, dict) or plan.get("medicinplan_id") != medicinplan_id:
        flash("API'en gav et uventet svar. Prøv igen om lidt.", "danger")
        return redirect(borger_url)
    if plan.get("borger_id") != borger_id:
        flash("Medicinplanen hører ikke til denne borger.", "warning")
        return redirect(borger_url)

    try:
        response = requests.post(
            f"{API_BASE_URL}/medicinudlevering/fyldning",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={
                "medicinplan_id": medicinplan_id,
                "startdato": request.form.get("startdato", ""),
                "antal": request.form.get("antal", type=int),
                "afhentningsfrist_minutter": request.form.get("afhentningsfrist_minutter", type=int),
            },
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Oprettelsen kunne ikke bekræftes. Kontrollér udleveringslisten, før du prøver igen.", "warning")
        return redirect(plan_url)

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 201:
        flash("Udleveringerne er oprettet.", "success")
        return redirect(plan_url)
    if response.status_code == 400:
        try:
            error = response.json()
        except ValueError:
            error = None
        message = error.get("message") if isinstance(error, dict) else None
        flash(message if isinstance(message, str) else "Kontrollér dato, antal og afhentningsfrist.", "warning")
    elif response.status_code == 422:
        flash("Vælg en gyldig dato og positive heltal til antal og afhentningsfrist.", "warning")
    elif response.status_code == 409:
        flash("Udleveringerne kunne ikke oprettes. Kontrollér den aktuelle udleveringsliste og de valgte datoer.", "warning")
    else:
        flash("Oprettelsen kunne ikke bekræftes. Kontrollér udleveringslisten, før du prøver igen.", "danger")
        return redirect(plan_url)
    return redirect(form_url)


# Pilledispenser routes
@app.route("/pilledispensere")
@app.doc(hide=True)
@login_required
def pilledispensere():
    """Vis alle dispensere og formularen til oprettelse eller redigering."""
    edit_pilledispenser_id = request.args.get("edit_pilledispenser_id", type=int)
    edit_pilledispenser = None

    try:
        dispenser_response = requests.get(
            f"{API_BASE_URL}/pilledispenser",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
        borger_response = requests.get(
            f"{API_BASE_URL}/borger",
            headers={"Authorization": f"Bearer {session['token']}"},
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        return render_template("error.html", message="Kan ikke kontakte API'en. Prøv igen om lidt."), 503

    if 401 in (dispenser_response.status_code, borger_response.status_code):
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if dispenser_response.status_code != 200 or borger_response.status_code != 200:
        return render_template("error.html", message="Kunne ikke hente dispensere og borgere. Prøv igen om lidt."), 502

    try:
        alle_pilledispensere = dispenser_response.json()
        alle_borgere = borger_response.json()
    except ValueError:
        return render_template("error.html", message="API'en gav et ugyldigt svar. Prøv igen om lidt."), 502
    if not isinstance(alle_pilledispensere, list) or not isinstance(alle_borgere, list):
        return render_template("error.html", message="API'en gav et uventet svar. Prøv igen om lidt."), 502

    # En borger kan kun have én dispenser. Ved redigering må den nuværende borger stadig vælges.
    optagne_borger_ids = []
    for dispenser in alle_pilledispensere:
        if dispenser["pilledispenser_id"] == edit_pilledispenser_id:
            edit_pilledispenser = dispenser
        else:
            optagne_borger_ids.append(dispenser["borger_id"])

    if edit_pilledispenser_id is not None and edit_pilledispenser is None:
        flash("Pilledispenseren findes ikke.", "warning")
        return redirect(url_for("pilledispensere"))

    valgbare_borgere = []
    for borger in alle_borgere:
        if borger["borger_id"] not in optagne_borger_ids:
            valgbare_borgere.append(borger)

    return render_template(
        "pilledispensere.html",
        pilledispensere=alle_pilledispensere,
        borgere=valgbare_borgere,
        edit_pilledispenser=edit_pilledispenser,
    )


@app.route("/pilledispensere/create", methods=["POST"])
@app.doc(hide=True)
@login_required
def create_pilledispenser():
    """Opret dispenseren hos API'et med den valgte borger."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/pilledispenser",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={
                "borger_id": request.form.get("borger_id", type=int),
                "enhed_id": request.form.get("enhed_id", "").strip(),
                "antal_rum": request.form.get("antal_rum", type=int),
                "drift_status": request.form.get("drift_status", ""),
            },
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Kontrollér oversigten, før du prøver igen.", "danger")
        return redirect(url_for("pilledispensere"))

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 201:
        flash("Pilledispenseren er oprettet og tildelt den valgte borger.", "success")
    elif response.status_code == 409:
        flash("Kontrollér borgeren og enheds-id'et. Enheds-id'et skal være unikt, og borgeren må kun have én dispenser.", "warning")
    elif response.status_code in (400, 422):
        flash("Kontrollér borger, enheds-id, antal rum og driftsstatus. Alle felter skal være udfyldt korrekt.", "warning")
    else:
        flash("Pilledispenseren kunne ikke oprettes. Prøv igen om lidt.", "danger")

    return redirect(url_for("pilledispensere"))


@app.route("/pilledispensere/update/<int:pilledispenser_id>", methods=["POST"])
@app.doc(hide=True)
@login_required
def update_pilledispenser(pilledispenser_id):
    """Gem dispenserens oplysninger og borgertildeling gennem API'et."""
    edit_url = url_for("pilledispensere", edit_pilledispenser_id=pilledispenser_id)

    try:
        response = requests.put(
            f"{API_BASE_URL}/pilledispenser/{pilledispenser_id}",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={
                "borger_id": request.form.get("borger_id", type=int),
                "enhed_id": request.form.get("enhed_id", "").strip(),
                "antal_rum": request.form.get("antal_rum", type=int),
                "drift_status": request.form.get("drift_status", ""),
                "aktiv": request.form.get("aktiv") == "true",
            },
            timeout=5,
            allow_redirects=False,
        )
    except requests.RequestException:
        flash("Kan ikke kontakte API'en. Kontrollér oversigten, før du prøver igen.", "danger")
        return redirect(edit_url)

    if response.status_code == 401:
        session.clear()
        flash("Dit login er udløbet eller ikke længere gyldigt. Log ind igen.", "warning")
        return redirect(url_for("login"))
    if response.status_code == 200:
        flash("Pilledispenseren er opdateret.", "success")
        return redirect(url_for("pilledispensere"))
    if response.status_code == 404:
        flash("Pilledispenseren findes ikke længere.", "warning")
        return redirect(url_for("pilledispensere"))
    if response.status_code == 409:
        flash("Kontrollér borgeren og enheds-id'et. Enheds-id'et skal være unikt, og borgeren må kun have én dispenser.", "warning")
    elif response.status_code in (400, 422):
        flash("Kontrollér borger, enheds-id, antal rum og driftsstatus. Alle felter skal være udfyldt korrekt.", "warning")
    else:
        flash("Pilledispenseren kunne ikke opdateres. Prøv igen om lidt.", "danger")

    return redirect(edit_url)


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

