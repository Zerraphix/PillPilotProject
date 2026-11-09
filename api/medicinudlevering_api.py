"""Manuel oprettelse og statusregistrering for alle borgeres udleveringer."""

from apiflask import APIBlueprint, Schema, abort
from apiflask.fields import DateTime, Integer, String
from apiflask.validators import Length, Range
from marshmallow.fields import AwareDateTime

from auth import auth
from database import medicinudlevering_db as database

api = APIBlueprint("medicinudlevering", __name__, url_prefix="/api/medicinudlevering")


class MedicinudleveringIn(Schema):
    """Vælg plan, dispenser og konkrete tidspunkter med UTC-offset."""
    medicinplan_id = Integer(required=True, validate=Range(min=1))
    pilledispenser_id = Integer(required=True, validate=Range(min=1))
    planlagt_tid = AwareDateTime(required=True)
    afhentningsfrist = AwareDateTime(required=True)


class MedicinudleveringFilter(Schema):
    """Udelad begge filtre for at hente alle udleveringer."""
    borger_id = Integer(load_default=None, allow_none=True, validate=Range(min=1))
    status_id = Integer(load_default=None, allow_none=True, validate=Range(min=1))


class StatusIn(Schema):
    """Vælg en status fra opslagstabellen. Udeladt tidspunkt betyder modtagelsestid."""
    status_id = Integer(required=True, validate=Range(min=1))
    tidspunkt = AwareDateTime(load_default=None, allow_none=True)
    fejlbeskrivelse = String(load_default=None, allow_none=True, validate=Length(max=2000))


class MedicinudleveringOut(Schema):
    """Udlevering med navne og statusbetydning, ikke kun fremmednøgler."""
    udlevering_id = Integer()
    medicinplan_id = Integer()
    pilledispenser_id = Integer()
    status_id = Integer()
    planlagt_tid = DateTime()
    afhentningsfrist = DateTime()
    udleveret_tid = DateTime(allow_none=True)
    afhentet_tid = DateTime(allow_none=True)
    fejlbeskrivelse = String(allow_none=True)
    oprettet_at = DateTime()
    status_kode = String()
    status_beskrivelse = String()
    medicinplan_navn = String()
    borger_id = Integer()
    borger_navn = String()
    kontaktperson_id = Integer()
    kontaktperson_navn = String()
    enhed_id = String()


@api.get("")
@api.auth_required(auth)
@api.input(MedicinudleveringFilter, location="query")
@api.output(MedicinudleveringOut(many=True))
def get_all(query_data: dict) -> list[dict]:
    """Hent alle udleveringer med valgfri filtrering på borger og status."""
    return database.all_medicinudleveringer(query_data["borger_id"], query_data["status_id"])


@api.get("/<int:udlevering_id>")
@api.auth_required(auth)
@api.output(MedicinudleveringOut)
def get_one(udlevering_id: int) -> dict:
    """Hent en enkelt udlevering."""
    row = database.get_medicinudlevering(udlevering_id)
    if row is None:
        abort(404, "Udleveringen findes ikke")
    return row


@api.post("")
@api.auth_required(auth)
@api.input(MedicinudleveringIn)
@api.output(MedicinudleveringOut, status_code=201)
def create(json_data: dict) -> dict:
    """Opret én planlagt udlevering. Dette drejer ikke dispenserens hjul."""
    udlevering_id = database.create_medicinudlevering(
        json_data["medicinplan_id"], json_data["pilledispenser_id"],
        json_data["planlagt_tid"], json_data["afhentningsfrist"]
    )
    return database.get_medicinudlevering(udlevering_id)


@api.patch("/<int:udlevering_id>/status")
@api.auth_required(auth)
@api.input(StatusIn)
@api.output(MedicinudleveringOut)
def change_status(udlevering_id: int, json_data: dict) -> dict:
    """Registrér et resultat manuelt. Brug statusopslaget til at vælge id'et."""
    changed = database.update_status(
        udlevering_id, json_data["status_id"],
        json_data["tidspunkt"], json_data["fejlbeskrivelse"]
    )
    if not changed:
        abort(404, "Udleveringen findes ikke")
    return database.get_medicinudlevering(udlevering_id)
