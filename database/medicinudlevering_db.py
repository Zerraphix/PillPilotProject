"""Udleveringer og deres status. Funktionerne sender ingen hardwarekommandoer."""

from datetime import datetime, timezone

from db import get_connection


def all_medicinudleveringer(
    borger_id: int | None = None, status_id: int | None = None
) -> list[dict]:
    """Hent alle udleveringer med navne. Filtre er valgfrie og afhænger ikke af login."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT u.*, s.kode AS status_kode, s.beskrivelse AS status_beskrivelse,
                   m.navn AS medicinplan_navn, m.borger_id,
                   b.fornavn || ' ' || b.efternavn AS borger_navn,
                   b.kontaktperson_id, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn,
                   p.enhed_id
            FROM public.medicinudlevering AS u
            JOIN public.udleveringsstatus AS s ON s.status_id = u.status_id
            JOIN public.medicinplan AS m ON m.medicinplan_id = u.medicinplan_id
            JOIN public.borger AS b ON b.borger_id = m.borger_id
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            JOIN public.pilledispenser AS p ON p.pilledispenser_id = u.pilledispenser_id
            WHERE ({borger_id}::integer IS NULL OR m.borger_id = {borger_id})
              AND ({status_id}::integer IS NULL OR u.status_id = {status_id})
            ORDER BY u.planlagt_tid DESC, u.udlevering_id DESC
        """).fetchall()


def get_medicinudlevering(udlevering_id: int) -> dict | None:
    """Hent én udlevering med status, borger, kontaktperson og enheds-id."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT u.*, s.kode AS status_kode, s.beskrivelse AS status_beskrivelse,
                   m.navn AS medicinplan_navn, m.borger_id,
                   b.fornavn || ' ' || b.efternavn AS borger_navn,
                   b.kontaktperson_id, k.fornavn || ' ' || k.efternavn AS kontaktperson_navn,
                   p.enhed_id
            FROM public.medicinudlevering AS u
            JOIN public.udleveringsstatus AS s ON s.status_id = u.status_id
            JOIN public.medicinplan AS m ON m.medicinplan_id = u.medicinplan_id
            JOIN public.borger AS b ON b.borger_id = m.borger_id
            JOIN public.kontaktperson AS k ON k.kontaktperson_id = b.kontaktperson_id
            JOIN public.pilledispenser AS p ON p.pilledispenser_id = u.pilledispenser_id
            WHERE u.udlevering_id = {udlevering_id}
        """).fetchone()


def create_medicinudlevering(
    medicinplan_id: int, pilledispenser_id: int,
    planlagt_tid: datetime, afhentningsfrist: datetime
) -> int:
    """Opret en planlagt udlevering, når borger, plan og dispenser passer sammen."""
    with get_connection() as conn:
        match = conn.execute(t"""
            SELECT m.borger_id
            FROM public.medicinplan AS m
            JOIN public.borger AS b ON b.borger_id = m.borger_id
            JOIN public.pilledispenser AS p ON p.borger_id = m.borger_id
            WHERE m.medicinplan_id = {medicinplan_id}
              AND p.pilledispenser_id = {pilledispenser_id}
              AND m.aktiv AND p.aktiv AND b.aktiv
            FOR SHARE OF m, p, b
        """).fetchone()
        if match is None:
            raise ValueError("Plan og dispenser skal findes, være aktive og tilhøre samme aktive borger.")
        status = conn.execute("""
            SELECT status_id FROM public.udleveringsstatus WHERE kode = 'planlagt'
        """).fetchone()
        if status is None:
            raise ValueError("Statuskoden planlagt mangler i udleveringsstatus.")
        row = conn.execute(t"""
            INSERT INTO public.medicinudlevering
                (medicinplan_id, pilledispenser_id, status_id, planlagt_tid, afhentningsfrist)
            VALUES ({medicinplan_id}, {pilledispenser_id}, {status['status_id']},
                    {planlagt_tid}, {afhentningsfrist})
            RETURNING udlevering_id
        """).fetchone()
        return row["udlevering_id"]


def update_status(
    udlevering_id: int, status_id: int,
    tidspunkt: datetime | None = None, fejlbeskrivelse: str | None = None
) -> bool:
    """Registrér status med enkle overgangsregler og bevar første registrerede tidspunkt.

    Rækken låses med FOR UPDATE, så to requests ikke ændrer samme udlevering samtidig.
    En gentaget statusbesked er uden effekt. Dette beskytter data, ikke motoren.
    """
    with get_connection() as conn:
        row = conn.execute(t"""
            SELECT u.*, s.kode
            FROM public.medicinudlevering AS u
            JOIN public.udleveringsstatus AS s ON s.status_id = u.status_id
            WHERE u.udlevering_id = {udlevering_id}
            FOR UPDATE OF u
        """).fetchone()
        if row is None:
            return False
        status = conn.execute(t"""
            SELECT kode FROM public.udleveringsstatus WHERE status_id = {status_id}
        """).fetchone()
        if status is None:
            raise ValueError("Det valgte status_id findes ikke.")
        ny_status = status["kode"]
        if ny_status == row["kode"]:
            return True
        tilladte_skift = {
            "planlagt": ["udleveret", "fejl", "annulleret"],
            "udleveret": ["afhentet", "ikke_afhentet", "fejl"],
            "ikke_afhentet": ["afhentet", "fejl"],
            "afhentet": [],
            "fejl": [],
            "annulleret": [],
        }
        if ny_status not in tilladte_skift.get(row["kode"], []):
            raise ValueError(f"Kan ikke skifte fra {row['kode']} til {ny_status}.")
        if tidspunkt is not None and ny_status not in ["udleveret", "afhentet"]:
            raise ValueError("tidspunkt bruges kun til udleveret og afhentet.")
        if fejlbeskrivelse is not None and ny_status != "fejl":
            raise ValueError("fejlbeskrivelse bruges kun ved status fejl.")
        if ny_status == "fejl" and not (fejlbeskrivelse or "").strip():
            raise ValueError("En fejl skal have en fejlbeskrivelse.")
        nu = datetime.now(timezone.utc)
        if ny_status == "ikke_afhentet" and nu < row["afhentningsfrist"]:
            raise ValueError("Afhentningsfristen er ikke overskredet endnu.")
        tidspunkt = tidspunkt or nu
        udleveret_tid = row["udleveret_tid"]
        afhentet_tid = row["afhentet_tid"]
        if ny_status == "udleveret":
            udleveret_tid = tidspunkt
        if ny_status == "afhentet":
            if udleveret_tid is None or tidspunkt < udleveret_tid:
                raise ValueError("Afhentning skal ligge efter en registreret udlevering.")
            afhentet_tid = tidspunkt
        conn.execute(t"""
            UPDATE public.medicinudlevering
            SET status_id = {status_id}, udleveret_tid = {udleveret_tid},
                afhentet_tid = {afhentet_tid}, fejlbeskrivelse = {fejlbeskrivelse}
            WHERE udlevering_id = {udlevering_id}
        """)
        return True
