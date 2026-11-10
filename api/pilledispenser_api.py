"""Fælles adgang til alle dispensere. Heartbeat kan afprøves manuelt."""

from apiflask import APIBlueprint, Schema, abort
from apiflask.fields import Boolean, DateTime, Integer, String
from apiflask.validators import Length, OneOf, Range

from auth import auth
from database import pilledispenser_db as database

api = APIBlueprint("pilledispenser", __name__, url_prefix="/api/pilledispenser")


class PilledispenserIn(Schema):
    """Borger og dispenseroplysninger vælges i requestet."""
    borger_id = Integer(required=True, validate=Range(min=1))
    enhed_id = String(required=True, validate=Length(min=1, max=100))
    antal_rum = Integer(required=True, validate=Range(min=1))
    drift_status = String(required=True, validate=OneOf(["klar", "offline", "fejl", "vedligeholdelse"]))


class PilledispenserUpdate(PilledispenserIn):
    """PUT kræver også dispenserens aktiv-flag."""
    aktiv = Boolean(required=True)


class PilledispenserFilter(Schema):
    """Et valgfrit borger-id. Udelad det for at se alle."""
    borger_id = Integer(load_default=None, allow_none=True, validate=Range(min=1))


class HeartbeatIn(Schema):
    """Den driftsstatus, der skal registreres sammen med modtagelsestiden."""
    drift_status = String(required=True, validate=OneOf(["klar", "offline", "fejl", "vedligeholdelse"]))


class PilledispenserOut(Schema):
    """Dispenserens data samt borgerens og kontaktpersonens navn."""
    pilledispenser_id = Integer()
    borger_id = Integer()
    enhed_id = String()
    antal_rum = Integer()
    drift_status = String()
    seneste_set_at = DateTime(allow_none=True)
    aktiv = Boolean()
    oprettet_at = DateTime()
    borger_navn = String()
    kontaktperson_id = Integer()
    kontaktperson_navn = String()


@api.get("")
@api.auth_required(auth)
@api.input(PilledispenserFilter, location="query")
@api.output(PilledispenserOut(many=True))
def get_all(query_data: dict) -> list[dict]:
    """Hent alle dispensere, eventuelt filtreret efter borger."""
    return database.all_pilledispensere(query_data["borger_id"])


@api.get("/<int:pilledispenser_id>")
@api.auth_required(auth)
@api.output(PilledispenserOut)
def get_one(pilledispenser_id: int) -> dict:
    """Hent én dispenser."""
    row = database.get_pilledispenser(pilledispenser_id)
    if row is None:
        abort(404, "Dispenseren findes ikke")
    return row


@api.post("")
@api.auth_required(auth)
@api.input(PilledispenserIn)
@api.output(PilledispenserOut, status_code=201)
def create(json_data: dict) -> dict:
    """Opret en dispenser og vælg dens borger."""
    pilledispenser_id = database.create_pilledispenser(
        json_data["borger_id"], json_data["enhed_id"],
        json_data["antal_rum"], json_data["drift_status"]
    )
    return database.get_pilledispenser(pilledispenser_id)


@api.put("/<int:pilledispenser_id>")
@api.auth_required(auth)
@api.input(PilledispenserUpdate)
@api.output(PilledispenserOut)
def update(pilledispenser_id: int, json_data: dict) -> dict:
    """Ret dispenserens oplysninger."""
    changed = database.update_pilledispenser(
        pilledispenser_id, json_data["borger_id"], json_data["enhed_id"],
        json_data["antal_rum"], json_data["drift_status"], json_data["aktiv"]
    )
    if not changed:
        abort(404, "Dispenseren findes ikke")
    return database.get_pilledispenser(pilledispenser_id)


@api.post("/<int:pilledispenser_id>/heartbeat")
@api.auth_required(auth)
@api.input(HeartbeatIn)
@api.output(PilledispenserOut)
def heartbeat(pilledispenser_id: int, json_data: dict) -> dict:
    """Registrér heartbeat manuelt med personalelogin. Ikke en motorstyring."""
    if not database.register_heartbeat(pilledispenser_id, json_data["drift_status"]):
        abort(404, "Dispenseren findes ikke")
    return database.get_pilledispenser(pilledispenser_id)


@api.delete("/<int:pilledispenser_id>")
@api.auth_required(auth)
@api.output({}, status_code=204)
def delete(pilledispenser_id: int):
    """Slet en ubrugt dispenser."""
    if not database.delete_pilledispenser(pilledispenser_id):
        abort(404, "Dispenseren findes ikke")
    return ""
