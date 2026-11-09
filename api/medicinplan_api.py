"""CRUD på alle medicinplaner. Borgeren vælges i requestet."""

from apiflask import APIBlueprint, Schema, abort
from apiflask.fields import Boolean, Date, DateTime, Integer, String, Time
from apiflask.validators import Length, Range

from auth import auth
from database import medicinplan_db as database

api = APIBlueprint("medicinplan", __name__, url_prefix="/api/medicinplan")


class MedicinplanIn(Schema):
    """Dagligt klokkeslæt i dansk lokal tid og planens datointerval."""
    borger_id = Integer(required=True, validate=Range(min=1))
    navn = String(required=True, validate=Length(min=1, max=100))
    tidspunkt = Time(required=True)
    startdato = Date(required=True)
    slutdato = Date(load_default=None, allow_none=True)


class MedicinplanUpdate(MedicinplanIn):
    """PUT kræver også planens aktiv-flag."""
    aktiv = Boolean(required=True)


class MedicinplanFilter(Schema):
    """Udelad borger_id for at hente alle borgeres planer."""
    borger_id = Integer(load_default=None, allow_none=True, validate=Range(min=1))


class MedicinplanOut(Schema):
    """Planen med borger, ansvarlig kontaktperson og faktisk opretter."""
    medicinplan_id = Integer()
    borger_id = Integer()
    navn = String()
    tidspunkt = Time()
    startdato = Date()
    slutdato = Date(allow_none=True)
    aktiv = Boolean()
    oprettet_af = Integer()
    oprettet_at = DateTime()
    borger_navn = String()
    kontaktperson_id = Integer()
    kontaktperson_navn = String()
    oprettet_af_navn = String()


@api.get("")
@api.auth_required(auth)
@api.input(MedicinplanFilter, location="query")
@api.output(MedicinplanOut(many=True))
def get_all(query_data: dict) -> list[dict]:
    """Hent alle medicinplaner, eventuelt filtreret efter borger."""
    return database.all_medicinplaner(query_data["borger_id"])


@api.get("/<int:medicinplan_id>")
@api.auth_required(auth)
@api.output(MedicinplanOut)
def get_one(medicinplan_id: int) -> dict:
    """Hent én medicinplan."""
    row = database.get_medicinplan(medicinplan_id)
    if row is None:
        abort(404, "Medicinplanen findes ikke")
    return row


@api.post("")
@api.auth_required(auth)
@api.input(MedicinplanIn)
@api.output(MedicinplanOut, status_code=201)
def create(json_data: dict) -> dict:
    """Opret en plan for en valgt borger. oprettet_af er den, der faktisk er logget ind."""
    if json_data["tidspunkt"].tzinfo is not None:
        abort(400, "tidspunkt skal være et lokalt klokkeslæt uden tidszone")
    medicinplan_id = database.create_medicinplan(
        json_data["borger_id"], json_data["navn"], json_data["tidspunkt"],
        json_data["startdato"], json_data["slutdato"], auth.current_user["kontaktperson_id"]
    )
    return database.get_medicinplan(medicinplan_id)


@api.put("/<int:medicinplan_id>")
@api.auth_required(auth)
@api.input(MedicinplanUpdate)
@api.output(MedicinplanOut)
def update(medicinplan_id: int, json_data: dict) -> dict:
    """Ret en plan. Den oprindelige opretter ændres ikke."""
    if json_data["tidspunkt"].tzinfo is not None:
        abort(400, "tidspunkt skal være et lokalt klokkeslæt uden tidszone")
    changed = database.update_medicinplan(
        medicinplan_id, json_data["borger_id"], json_data["navn"], json_data["tidspunkt"],
        json_data["startdato"], json_data["slutdato"], json_data["aktiv"]
    )
    if not changed:
        abort(404, "Medicinplanen findes ikke")
    return database.get_medicinplan(medicinplan_id)


@api.delete("/<int:medicinplan_id>")
@api.auth_required(auth)
@api.output({}, status_code=204)
def delete(medicinplan_id: int):
    """Slet en ubrugt plan. Brug aktiv=false, hvis den skal bevares."""
    if not database.delete_medicinplan(medicinplan_id):
        abort(404, "Medicinplanen findes ikke")
    return ""
