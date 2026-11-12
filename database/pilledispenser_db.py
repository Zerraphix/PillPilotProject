"""Dispensernes SQL med borger og ansvarlig kontaktperson."""

from db import get_connection


def all_pilledispensere(borger_id: int | None = None) -> list[dict]:
    """Hent alle dispensere, eller filtrér på en bestemt borger."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT p.*, b.fornavn || ' ' || b.efternavn AS borger_navn,
                   b.kontaktperson_id, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn
            FROM public.pilledispenser AS p
            JOIN public.borger AS b ON b.borger_id = p.borger_id
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            WHERE ({borger_id}::integer IS NULL OR p.borger_id = {borger_id})
            ORDER BY p.pilledispenser_id
        """).fetchall()


def get_pilledispenser(pilledispenser_id: int) -> dict | None:
    """Hent en dispenser med navnet på borgeren og kontaktpersonen."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT p.*, b.fornavn || ' ' || b.efternavn AS borger_navn,
                   b.kontaktperson_id, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn
            FROM public.pilledispenser AS p
            JOIN public.borger AS b ON b.borger_id = p.borger_id
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            WHERE p.pilledispenser_id = {pilledispenser_id}
        """).fetchone()


def create_pilledispenser(borger_id: int, enhed_id: str, antal_rum: int, drift_status: str) -> int:
    """Opret en dispenser med den valgte borger."""
    with get_connection() as conn:
        row = conn.execute(t"""
            INSERT INTO public.pilledispenser (borger_id, enhed_id, antal_rum, drift_status)
            VALUES ({borger_id}, {enhed_id}, {antal_rum}, {drift_status})
            RETURNING pilledispenser_id
        """).fetchone()
        return row["pilledispenser_id"]


def update_pilledispenser(
    pilledispenser_id: int, borger_id: int, enhed_id: str,
    antal_rum: int, drift_status: str, aktiv: bool
) -> bool:
    """Ret konfigurationen. Dette sender ingen kommandoer til hardwaren."""
    with get_connection() as conn:
        dispenser = conn.execute(t"""
            SELECT borger_id, antal_rum FROM public.pilledispenser
            WHERE pilledispenser_id = {pilledispenser_id}
            FOR UPDATE
        """).fetchone()
        if dispenser is None:
            return False
        if dispenser["borger_id"] != borger_id or dispenser["antal_rum"] != antal_rum:
            aaben_udlevering = conn.execute(t"""
                SELECT u.udlevering_id
                FROM public.medicinudlevering AS u
                JOIN public.udleveringsstatus AS s ON s.status_id = u.status_id
                WHERE u.pilledispenser_id = {pilledispenser_id}
                  AND s.kode IN ('planlagt', 'udleveret', 'ikke_afhentet')
                LIMIT 1
            """).fetchone()
            if aaben_udlevering is not None:
                raise ValueError("Borger og antal rum kan ikke ændres, mens dispenseren har åbne udleveringer.")

        cursor = conn.execute(t"""
            UPDATE public.pilledispenser
            SET borger_id = {borger_id}, enhed_id = {enhed_id}, antal_rum = {antal_rum},
                drift_status = {drift_status}, aktiv = {aktiv}
            WHERE pilledispenser_id = {pilledispenser_id}
        """)
        return cursor.rowcount == 1


def register_heartbeat(pilledispenser_id: int, drift_status: str) -> bool:
    """Gem serverens modtagelsestid og en rapporteret driftsstatus."""
    with get_connection() as conn:
        cursor = conn.execute(t"""
            UPDATE public.pilledispenser
            SET seneste_set_at = CURRENT_TIMESTAMP, drift_status = {drift_status}
            WHERE pilledispenser_id = {pilledispenser_id}
        """)
        return cursor.rowcount == 1


def delete_pilledispenser(pilledispenser_id: int) -> bool:
    """Slet en dispenser, hvis ingen udleveringer henviser til den."""
    with get_connection() as conn:
        cursor = conn.execute(t"""
            DELETE FROM public.pilledispenser WHERE pilledispenser_id = {pilledispenser_id}
        """)
        return cursor.rowcount == 1
