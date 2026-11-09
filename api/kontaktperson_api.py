"""Kontaktpersoner kan se, oprette og ændre alle kontaktpersoner."""

from apiflask import APIBlueprint, Schema, abort
from apiflask.fields import Boolean, DateTime, Email, Integer, String
from apiflask.validators import Length

from auth import auth
from database import kontaktperson_db as database

api = APIBlueprint("kontaktperson", __name__, url_prefix="/api/kontaktperson")


class KontaktpersonIn(Schema):
    """Kontaktoplysninger, som klienten må angive."""
    fornavn = String(required=True, validate=Length(min=1, max=100))
    efternavn = String(required=True, validate=Length(min=1, max=100))
    email = Email(required=True, validate=Length(max=250))
    telefon = String(load_default=None, allow_none=True, validate=Length(max=25))


class KontaktpersonCreate(KontaktpersonIn):
    """Ved oprettelse skal der også vælges et password."""
    password = String(required=True, validate=Length(min=12, max=128), load_only=True)


class KontaktpersonUpdate(KontaktpersonIn):
    """PUT erstatter kontaktoplysningerne og kræver et aktiv-flag."""
    aktiv = Boolean(required=True)


class PasswordIn(Schema):
    """Et nyt password til den valgte kontaktperson."""
    password = String(required=True, validate=Length(min=12, max=128), load_only=True)


class KontaktpersonOut(Schema):
    """Offentlige personalefelter til indloggede brugere, aldrig password-hash."""
    kontaktperson_id = Integer()
    fornavn = String()
    efternavn = String()
    email = String()
    telefon = String(allow_none=True)
    aktiv = Boolean()
    oprettet_at = DateTime()


@api.get("")
@api.auth_required(auth)
@api.output(KontaktpersonOut(many=True))
def get_all() -> list[dict]:
    """Hent alle kontaktpersoner, også inaktive."""
    return database.all_kontaktpersoner()


@api.get("/<int:kontaktperson_id>")
@api.auth_required(auth)
@api.output(KontaktpersonOut)
def get_one(kontaktperson_id: int) -> dict:
    """Hent kontaktoplysninger på én vilkårlig kontaktperson."""
    row = database.get_kontaktperson(kontaktperson_id)
    if row is None:
        abort(404, "Kontaktpersonen findes ikke")
    return row


@api.post("")
@api.auth_required(auth)
@api.input(KontaktpersonCreate)
@api.output(KontaktpersonOut, status_code=201)
def create(json_data: dict) -> dict:
    """Opret en ny kontaktperson gennem API'et."""
    kontaktperson_id = database.create_kontaktperson(
        json_data["fornavn"], json_data["efternavn"], json_data["email"],
        json_data["password"], json_data["telefon"]
    )
    return database.get_kontaktperson(kontaktperson_id)


@api.put("/<int:kontaktperson_id>")
@api.auth_required(auth)
@api.input(KontaktpersonUpdate)
@api.output(KontaktpersonOut)
def update(kontaktperson_id: int, json_data: dict) -> dict:
    """Ret navn, kontaktoplysninger og aktiv-flag på den valgte kontaktperson."""
    changed = database.update_kontaktperson(
        kontaktperson_id, json_data["fornavn"], json_data["efternavn"],
        json_data["email"], json_data["aktiv"], json_data["telefon"]
    )
    if not changed:
        abort(404, "Kontaktpersonen findes ikke")
    return database.get_kontaktperson(kontaktperson_id)


@api.patch("/<int:kontaktperson_id>/password")
@api.auth_required(auth)
@api.input(PasswordIn)
def change_password(kontaktperson_id: int, json_data: dict) -> dict:
    """Sæt nyt password. Alle kontaktpersoner er betroet samme rettigheder."""
    if not database.update_password(kontaktperson_id, json_data["password"]):
        abort(404, "Kontaktpersonen findes ikke")
    return {"message": "Password er ændret"}


@api.delete("/<int:kontaktperson_id>")
@api.auth_required(auth)
@api.output({}, status_code=204)
def delete(kontaktperson_id: int):
    """Slet en ubrugt kontaktperson. Relationer kan blokere sletningen."""
    if not database.delete_kontaktperson(kontaktperson_id):
        abort(404, "Kontaktpersonen findes ikke")
    return ""
