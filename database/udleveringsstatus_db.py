"""Læs de seks statusser, som oprettes af schema.sql."""

from db import get_connection


def all_statusser() -> list[dict]:
    """Hent id, kode og forklaring for alle statusser."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM public.udleveringsstatus ORDER BY status_id").fetchall()


def get_status(status_id: int) -> dict | None:
    """Hent én status eller None."""
    with get_connection() as conn:
        return conn.execute(t"""
            SELECT * FROM public.udleveringsstatus WHERE status_id = {status_id}
        """).fetchone()
