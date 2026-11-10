"""Alle indloggede kontaktpersoner kan administrere alle borgere."""

from apiflask import APIBlueprint, Schema, abort
from apiflask.fields import Boolean, DateTime, Integer, String, Nested
from apiflask.validators import Length, Range

from auth import auth
from database import borger_db as database
from database import medicinplan_db as medicinplan_database
from api.medicinplan_api import MedicinplanOut
from database import medicinudlevering_db as udlevering_database
from api.medicinudlevering_api import MedicinudleveringOut
from database import pilledispenser_db as dispenser_database
from api.pilledispenser_api import PilledispenserOut

api = APIBlueprint("borger", __name__, url_prefix="/api/borger")


class BorgerIn(Schema):
    """Kontaktpersonen vælges eksplicit, uafhængigt af login."""
    kontaktperson_id = Integer(required=True, validate=Range(min=1))
    fornavn = String(required=True, validate=Length(min=1, max=100))
    efternavn = String(required=True, validate=Length(min=1, max=100))
    telefon = String(load_default=None, allow_none=True, validate=Length(max=25))


class BorgerUpdate(BorgerIn):
    """PUT erstatter felterne og kræver et aktiv-flag."""
    aktiv = Boolean(required=True)


class BorgerFilter(Schema):
    """Udelad filteret for at se alle kontaktpersoners borgere."""
    kontaktperson_id = Integer(load_default=None, allow_none=True, validate=Range(min=1))


class BorgerOut(Schema):
    """Borgeren samt kontaktpersonens navn, telefon og email."""
    borger_id = Integer()
    kontaktperson_id = Integer()
    fornavn = String()
    efternavn = String()
    telefon = String(allow_none=True)
    aktiv = Boolean()
    oprettet_at = DateTime()
    kontaktperson_navn = String()
    kontaktperson_email = String()
    kontaktperson_telefon = String(allow_none=True)
    kontaktperson_aktiv = Boolean()


@api.get("")
@api.auth_required(auth)
@api.input(BorgerFilter, location="query")
@api.output(BorgerOut(many=True))
def get_all(query_data: dict) -> list[dict]:
    """Hent alle borgere, eventuelt filtreret efter kontaktperson_id."""
    return database.all_borgere(query_data["kontaktperson_id"])


@api.get("/<int:borger_id>")
@api.auth_required(auth)
@api.output(BorgerOut)
def get_one(borger_id: int) -> dict:
    """Hent én borger, også en kollegas borger."""
    row = database.get_borger(borger_id)
    if row is None:
        abort(404, "Borgeren findes ikke")
    return row


@api.post("")
@api.auth_required(auth)
@api.input(BorgerIn)
@api.output(BorgerOut, status_code=201)
def create(json_data: dict) -> dict:
    """Opret en borger med et selvvalgt kontaktperson_id."""
    borger_id = database.create_borger(
        json_data["kontaktperson_id"], json_data["fornavn"],
        json_data["efternavn"], json_data["telefon"]
    )
    return database.get_borger(borger_id)


@api.put("/<int:borger_id>")
@api.auth_required(auth)
@api.input(BorgerUpdate)
@api.output(BorgerOut)
def update(borger_id: int, json_data: dict) -> dict:
    """Ret borgeren eller flyt ansvaret til en anden kontaktperson."""
    changed = database.update_borger(
        borger_id, json_data["kontaktperson_id"], json_data["fornavn"],
        json_data["efternavn"], json_data["aktiv"], json_data["telefon"]
    )
    if not changed:
        abort(404, "Borgeren findes ikke")
    return database.get_borger(borger_id)


@api.delete("/<int:borger_id>")
@api.auth_required(auth)
@api.output({}, status_code=204)
def delete(borger_id: int):
    """Slet en ubrugt borger. Databasens relationer beskytter historikken."""
    if not database.delete_borger(borger_id):
        abort(404, "Borgeren findes ikke")
    return ""


class BorgerOversigtOut(Schema):
    """Samme data som de enkelte GET-endpoints, samlet i ét svar."""
    borger = Nested(BorgerOut)
    pilledispensere = Nested(PilledispenserOut, many=True)
    medicinplaner = Nested(MedicinplanOut, many=True)
    medicinudleveringer = Nested(MedicinudleveringOut, many=True)


@api.get("/<int:borger_id>/oversigt")
@api.auth_required(auth)
@api.output(BorgerOversigtOut)
def oversigt(borger_id: int) -> dict:
    """Hent borger, dispenser, planer og udleveringer i ét API-kald."""
    borger = database.get_borger(borger_id)
    if borger is None:
        abort(404, "Borgeren findes ikke")
    return {
        "borger": borger,
        "pilledispensere": dispenser_database.all_pilledispensere(borger_id),
        "medicinplaner": medicinplan_database.all_medicinplaner(borger_id),
        "medicinudleveringer": udlevering_database.all_medicinudleveringer(borger_id),
    }
