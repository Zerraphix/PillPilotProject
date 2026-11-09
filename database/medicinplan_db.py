"""SQL til medicinplaner. Oprettelsen knyttes til den faktiske indloggede person."""

from datetime import date, time

from db import get_connection


def all_medicinplaner(borger_id: int | None = None) -> list[dict]:
    """Hent alle planer med borger, ansvarlig kontaktperson og opretter."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT m.*, b.fornavn || ' ' || b.efternavn AS borger_navn,
                   b.kontaktperson_id, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn,
                   o.fornavn || ' ' || o.efternavn AS oprettet_af_navn
            FROM public.medicinplan AS m
            JOIN public.borger AS b ON b.borger_id = m.borger_id
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            JOIN public.kontaktperson AS o ON o.kontaktperson_id = m.oprettet_af
            WHERE ({borger_id}::integer IS NULL OR m.borger_id = {borger_id})
            ORDER BY m.medicinplan_id
        """).fetchall()


def get_medicinplan(medicinplan_id: int) -> dict | None:
    """Hent én medicinplan med navne fra de tilknyttede tabeller."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT m.*, b.fornavn || ' ' || b.efternavn AS borger_navn,
                   b.kontaktperson_id, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn,
                   o.fornavn || ' ' || o.efternavn AS oprettet_af_navn
            FROM public.medicinplan AS m
            JOIN public.borger AS b ON b.borger_id = m.borger_id
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            JOIN public.kontaktperson AS o ON o.kontaktperson_id = m.oprettet_af
            WHERE m.medicinplan_id = {medicinplan_id}
        """).fetchone()


def create_medicinplan(
    borger_id: int, navn: str, tidspunkt: time, startdato: date,
    slutdato: date | None, oprettet_af: int
) -> int:
    """Opret en daglig medicinplan. Der oprettes ikke automatisk udleveringer."""
    with get_connection() as conn:
        row = conn.execute(t"""
            INSERT INTO public.medicinplan
                (borger_id, navn, tidspunkt, startdato, slutdato, oprettet_af)
            VALUES ({borger_id}, {navn}, {tidspunkt}, {startdato}, {slutdato}, {oprettet_af})
            RETURNING medicinplan_id
        """).fetchone()
        return row["medicinplan_id"]


def update_medicinplan(
    medicinplan_id: int, borger_id: int, navn: str, tidspunkt: time,
    startdato: date, slutdato: date | None, aktiv: bool
) -> bool:
    """Ret planen, men flyt aldrig eksisterende udleveringshistorik til en anden borger."""
    with get_connection() as conn:
        plan = conn.execute(t"""
            SELECT borger_id FROM public.medicinplan
            WHERE medicinplan_id = {medicinplan_id} FOR UPDATE
        """).fetchone()
        if plan is None:
            return False
        if plan["borger_id"] != borger_id:
            udlevering = conn.execute(t"""
                SELECT udlevering_id FROM public.medicinudlevering
                WHERE medicinplan_id = {medicinplan_id} LIMIT 1
            """).fetchone()
            if udlevering is not None:
                raise ValueError("En plan med udleveringer kan ikke flyttes til en anden borger.")
        conn.execute(t"""
            UPDATE public.medicinplan
            SET borger_id = {borger_id}, navn = {navn}, tidspunkt = {tidspunkt},
                startdato = {startdato}, slutdato = {slutdato}, aktiv = {aktiv}
            WHERE medicinplan_id = {medicinplan_id}
        """)
        return True


def delete_medicinplan(medicinplan_id: int) -> bool:
    """Slet en ubrugt plan. Planer med udleveringer beskyttes af fremmednøglen."""
    with get_connection() as conn:
        cursor = conn.execute(t"""
            DELETE FROM public.medicinplan WHERE medicinplan_id = {medicinplan_id}
        """)
        return cursor.rowcount == 1
