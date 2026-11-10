"""Kontaktpersonernes SQL. Password-hash bruges kun internt ved login."""

from werkzeug.security import generate_password_hash

from db import get_connection

def all_kontaktpersoner() -> list[dict]:
    """Hent alle kontaktpersoner uden password-hash, også inaktive."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT kontaktperson_id, fornavn, efternavn, email, telefon, aktiv, oprettet_at
            FROM public.kontaktperson
            ORDER BY kontaktperson_id
        """).fetchall()


def get_kontaktperson(kontaktperson_id: int) -> dict | None:
    """Hent én kontaktperson uden password-hash."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT kontaktperson_id, fornavn, efternavn, email, telefon, aktiv, oprettet_at
            FROM public.kontaktperson
            WHERE kontaktperson_id = {kontaktperson_id}
        """).fetchone()
        
        
def get_login_kontaktperson(email: str | None, kontaktperson_id: int | None) -> dict | None:
    """Hent hash til login med enten email eller id. Må ikke sendes som API-svar."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT kontaktperson_id, password_hash, aktiv
            FROM public.kontaktperson
            WHERE email = {email} OR kontaktperson_id = {kontaktperson_id}
        """).fetchone()


def create_kontaktperson(
    fornavn: str, efternavn: str, email: str, password: str, telefon: str | None = None
) -> int:
    """Hash password, opret kontaktpersonen, og returnér det nye id."""
    password_hash = generate_password_hash(password)
    with get_connection() as conn:
        row = conn.execute(t"""
            INSERT INTO public.kontaktperson (fornavn, efternavn, email, password_hash, telefon)
            VALUES ({fornavn}, {efternavn}, {email}, {password_hash}, {telefon})
            RETURNING kontaktperson_id
        """).fetchone()
        return row["kontaktperson_id"]


def update_kontaktperson(
    kontaktperson_id: int, fornavn: str, efternavn: str, email: str,
    aktiv: bool, telefon: str | None = None
) -> bool:
    """Opdatér kontaktoplysninger og aktiv-flag, men ikke password."""
    with get_connection() as conn:
        cursor = conn.execute(t"""
            UPDATE public.kontaktperson
            SET fornavn = {fornavn}, efternavn = {efternavn}, email = {email},
                telefon = {telefon}, aktiv = {aktiv}
            WHERE kontaktperson_id = {kontaktperson_id}
        """)
        return cursor.rowcount == 1


def update_password(kontaktperson_id: int, password: str) -> bool:
    """Gem et nyt password-hash. Det nye password returneres aldrig."""
    password_hash = generate_password_hash(password)
    with get_connection() as conn:
        cursor = conn.execute(t"""
            UPDATE public.kontaktperson SET password_hash = {password_hash}
            WHERE kontaktperson_id = {kontaktperson_id}
        """)
        return cursor.rowcount == 1


def delete_kontaktperson(kontaktperson_id: int) -> bool:
    """Slet kontaktpersonen, hvis ingen fremmednøgler henviser til personen."""
    with get_connection() as conn:
        cursor = conn.execute(t"""
            DELETE FROM public.kontaktperson WHERE kontaktperson_id = {kontaktperson_id}
        """)
        return cursor.rowcount == 1
