"""Borgernes SQL med JOIN til den aktuelt ansvarlige kontaktperson."""

from datetime import date

from db import get_connection


def all_borgere(kontaktperson_id: int | None = None) -> list[dict]:
    """Hent alle borgere, eller filtrér efter en valgfri kontaktperson."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT b.*, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn,
                   k.email AS kontaktperson_email, k.telefon AS kontaktperson_telefon,
                   k.aktiv AS kontaktperson_aktiv
            FROM public.borger AS b
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            WHERE ({kontaktperson_id}::integer IS NULL OR b.kontaktperson_id = {kontaktperson_id})
            ORDER BY b.borger_id
        """).fetchall()


def get_borger(borger_id: int) -> dict | None:
    """Hent én borger og oplysninger om borgerens kontaktperson."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT b.*, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn,
                   k.email AS kontaktperson_email, k.telefon AS kontaktperson_telefon,
                   k.aktiv AS kontaktperson_aktiv
            FROM public.borger AS b
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            WHERE b.borger_id = {borger_id}
        """).fetchone()


def create_borger(
    kontaktperson_id: int, fornavn: str, efternavn: str, birthday: date, telefon: str, adresse: str, diagnose: str, allergi: str | None = None
) -> int:
    """Opret en borger med den kontaktperson, som er valgt i requestet."""
    with get_connection() as conn:
        row = conn.execute(t"""
            INSERT INTO public.borger (kontaktperson_id, fornavn, efternavn, birthday, telefon, adresse, diagnose, allergi)
            VALUES ({kontaktperson_id}, {fornavn}, {efternavn}, {birthday}, {telefon}, {adresse}, {diagnose}, {allergi})
            RETURNING borger_id
        """).fetchone()
        return row["borger_id"]


def update_borger(
    borger_id: int, kontaktperson_id: int, fornavn: str, efternavn: str, birthday: date,
    telefon: str, adresse: str, diagnose: str, allergi: str, aktiv: bool | None = None
) -> bool:
    """Ret borgeren. Den ansvarlige kontaktperson kan også ændres."""
    with get_connection() as conn:
        cursor = conn.execute(t"""
            UPDATE public.borger
            SET kontaktperson_id = {kontaktperson_id}, fornavn = {fornavn},
                efternavn = {efternavn}, birthday = {birthday}, telefon = {telefon},
                adresse = {adresse}, diagnose = {diagnose}, allergi = {allergi}, aktiv = {aktiv}
            WHERE borger_id = {borger_id}
        """)
        return cursor.rowcount == 1


def delete_borger(borger_id: int) -> bool:
    """Slet kun en borger uden relationer. Brug ellers aktiv=false."""
    with get_connection() as conn:
        cursor = conn.execute(t"DELETE FROM public.borger WHERE borger_id = {borger_id}")
        return cursor.rowcount == 1
