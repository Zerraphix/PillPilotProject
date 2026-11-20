"""Opret en hemmelig API-nøgle til en eksisterende pilledispenser, én gang.

Kør fra hjemmesiden/: uv run --env-file .env python opret_enhedsnoegle.py
Gem nøglen sikkert, og del den ikke i Git eller screenshots.
"""

import hashlib
import secrets

from db import get_connection


def main():
    enhed_id = input("Enhed-ID: ").strip()
    if not enhed_id:
        print("Du skal angive enhed_id.")
        return

    with get_connection() as conn:
        row = conn.execute(
            "SELECT enhed_id, api_key_hash FROM public.pilledispenser "
            "WHERE enhed_id = %s AND aktiv = TRUE FOR UPDATE",
            (enhed_id,),
        ).fetchone()

        if row is None:
            print("Ingen aktiv pilledispenser med dette enhed_id.")
            return
        if row["api_key_hash"] is not None:
            print("Denne dispenser har allerede en nøgle. Ingen ændring foretaget.")
            return

        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        conn.execute(
            "UPDATE public.pilledispenser SET api_key_hash = %s WHERE enhed_id = %s",
            (key_hash, enhed_id),
        )

    print("API-nøgle oprettet til", enhed_id)
    print("Gem denne nøgle sikkert (vises kun nu):", api_key)


if __name__ == "__main__":
    main()
