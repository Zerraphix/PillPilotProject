"""Læs databasen og kontrollér tabeller, kolonner og de seks standardstatusser.

Kør fra projektmappen:
    uv run --env-file .env check_database.py

Der oprettes, ændres eller slettes ingen rækker. Testen erstatter ikke en
integrationstest af alle SQL-funktioner og constraints.
"""

import logging

import psycopg

from db import get_connection

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = {
    "kontaktperson": (
        "kontaktperson_id", "fornavn", "efternavn", "email", "password_hash",
        "telefon", "aktiv", "oprettet_at",
    ),
    "borger": (
        "borger_id", "kontaktperson_id", "fornavn", "efternavn", "telefon",
        "aktiv", "oprettet_at",
    ),
    "pilledispenser": (
        "pilledispenser_id", "borger_id", "enhed_id", "antal_rum", "drift_status",
        "seneste_set_at", "aktiv", "oprettet_at",
    ),
    "medicinplan": (
        "medicinplan_id", "borger_id", "navn", "tidspunkt", "startdato",
        "slutdato", "aktiv", "oprettet_af", "oprettet_at",
    ),
    "udleveringsstatus": ("status_id", "kode", "beskrivelse"),
    "medicinudlevering": (
        "udlevering_id", "medicinplan_id", "pilledispenser_id", "status_id",
        "planlagt_tid", "afhentningsfrist", "udleveret_tid", "afhentet_tid",
        "fejlbeskrivelse", "oprettet_at",
    ),
}
EXPECTED_STATUSES = {
    "planlagt", "udleveret", "ikke_afhentet", "afhentet", "fejl", "annulleret",
}


def check_database() -> bool:
    """Sammenlign synlige kolonner og statuskoder med det vedlagte schema."""
    correct = True
    with get_connection() as conn:
        for table, expected in EXPECTED_COLUMNS.items():
            query = t"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = {table}
                ORDER BY ordinal_position
            """
            actual = tuple(row[0] for row in conn.execute(query).fetchall())
            if actual == expected:
                logger.info("OK: %s", table)
            else:
                correct = False
                logger.error("Afvigelse i %s", table)
                logger.error("Forventet: %s", expected)
                logger.error("Fundet: %s", actual)

        if not correct:
            return False

        actual_statuses = {
            row[0] for row in conn.execute(
                "SELECT kode FROM public.udleveringsstatus"
            ).fetchall()
        }
        if actual_statuses != EXPECTED_STATUSES:
            logger.error("Statuskoderne afviger fra schema.sql.")
            logger.error("Forventet: %s", sorted(EXPECTED_STATUSES))
            logger.error("Fundet: %s", sorted(actual_statuses))
            return False
        logger.info("OK: Alle seks standardstatusser findes.")
    return True


def main() -> int:
    """Kør en læsende kontrol og returnér 0 ved succes eller 1 ved fejl."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        correct = check_database()
    except psycopg.Error as error:
        logger.error("Databasefejl:\n%s", error)
        return 1
    if correct:
        logger.info("Kontrol gennemført uden at ændre data.")
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
