"""Engangsoprettelse af den første kontaktperson, kun på en tom kontaktpersontabel.

Kør: uv run --env-file .env opret_foerste_kontaktperson.py
Derefter oprettes alle nye kontaktpersoner med POST /api/kontaktperson.
Filen sletter ingen data og indeholder ingen faste passwords.
"""

from getpass import getpass

from database import kontaktperson_db
from password_validation import PASSWORD_ERROR, validate_password


def main() -> None:
    """Spørg efter første konto. En eksisterende konto skal i stedet bruges til login."""
    if kontaktperson_db.all_kontaktpersoner():
        print("Der findes allerede kontaktpersoner. Log ind og brug POST /api/kontaktperson.")
        return
    fornavn = input("Fornavn: ").strip()
    efternavn = input("Efternavn: ").strip()
    email = input("Email: ").strip()
    telefon = input("Telefon, valgfri: ").strip() or None
    print(PASSWORD_ERROR)
    password = getpass("Password: ")
    gentaget = getpass("Gentag password: ")
    if not fornavn or not efternavn or "@" not in email:
        print("Udfyld navn og en email-adresse.")
        return
    if password != gentaget:
        print("Password skal være ens begge gange.")
        return
    try:
        validate_password(password)
    except ValueError as error:
        print(error)
        return
    kontaktperson_id = kontaktperson_db.create_kontaktperson(fornavn, efternavn, email, password, telefon)
    print(f"Kontaktperson {kontaktperson_id} er oprettet. Log ind i Swagger på /docs.")


if __name__ == "__main__":
    main()
