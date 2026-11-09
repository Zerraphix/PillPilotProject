"""Opslag i statusser. Statuskoderne er faste, fordi Python-logikken bruger dem."""

from apiflask import APIBlueprint, Schema, abort
from apiflask.fields import Integer, String

from auth import auth
from database import udleveringsstatus_db as database

api = APIBlueprint("udleveringsstatus", __name__, url_prefix="/api/udleveringsstatus")


class UdleveringsstatusOut(Schema):
    """Det id, som bruges ved statusændring, og kodens betydning."""
    status_id = Integer()
    kode = String()
    beskrivelse = String()


@api.get("")
@api.auth_required(auth)
@api.output(UdleveringsstatusOut(many=True))
def get_all() -> list[dict]:
    """Hent alle seks udleveringsstatusser."""
    return database.all_statusser()


@api.get("/<int:status_id>")
@api.auth_required(auth)
@api.output(UdleveringsstatusOut)
def get_one(status_id: int) -> dict:
    """Hent én status."""
    row = database.get_status(status_id)
    if row is None:
        abort(404, "Status findes ikke")
    return row
