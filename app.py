"""Start PillPilot: uv run --env-file .env flask --app app run --debug.

Swagger ligger på /docs. Appen opretter eller sletter aldrig tabeller ved opstart.
"""

import logging

import psycopg
from apiflask import APIFlask, Schema, abort
from apiflask.fields import Email, Integer, String
from apiflask.validators import Length, Range

from auth import auth, check_login, create_token
from api.borger_api import api as borger_api
from api.kontaktperson_api import KontaktpersonOut, api as kontaktperson_api
from api.medicinplan_api import api as medicinplan_api
from api.medicinudlevering_api import api as medicinudlevering_api
from api.pilledispenser_api import api as pilledispenser_api
from api.udleveringsstatus_api import api as udleveringsstatus_api

logger = logging.getLogger(__name__)
app = APIFlask(__name__, title="PillPilot API")
app.json.ensure_ascii = False
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
    password = String(required=True, validate=Length(min=1, max=128), load_only=True)


class TokenOut(Schema):
    """Tokenet kopieres til Authorize i Swagger uden at tilføje Bearer."""
    token = String()


@app.post("/api/auth/login")
@app.input(LoginIn)
@app.output(TokenOut)
def login(json_data: dict) -> dict:
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

