"""Fælles PostgreSQL-forbindelse. Filen kører aldrig schema.sql."""

import os

import psycopg
from psycopg.rows import dict_row


def get_connection() -> psycopg.Connection:
    """Åbn en forbindelse, hvor hver række returneres som en dictionary.

    DATABASE_URL bruges, hvis den er sat. Ellers bruges PG*-variablerne.
    .env indlæses med uv run --env-file .env, ikke af denne funktion.
    """
    if os.environ.get("DATABASE_URL"):
        return psycopg.connect(
            os.environ["DATABASE_URL"], row_factory=dict_row, connect_timeout=5
        )
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "PillPilotDB"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD"),
        row_factory=dict_row,
        connect_timeout=5,
    )


if __name__ == "__main__":
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT current_database() AS database, current_user AS bruger"
            ).fetchone()
        print(f"Forbundet til {row['database']} som {row['bruger']}.")
    except psycopg.OperationalError:
        raise SystemExit("Ingen forbindelse. Kontrollér .env og at PostgreSQL-serveren kører.")
