
import time
from datetime import datetime, timezone
from threading import Lock

# Gemmer seneste data i RAM
live_data = {}
lock = Lock()

OFFLINE_TIMEOUT = 60


def update_live_status(message):
    """Opdaterer live-data fra en pilledispenser."""

    if message["type"] != "status":
        return False

    enhed_id = message["enhed_id"]
    device = message["device"]
    data = message["data"]

    # Kontrollér batteriprocent fra armbåndet
    if device == "armbaand":
        battery = data.get("battery_pct")

        if type(battery) is not int or not 0 <= battery <= 100:
            raise ValueError("Ugyldig batteriprocent")

    with lock:
        if enhed_id not in live_data:
            live_data[enhed_id] = {}

        live_data[enhed_id][device] = {
            "data": data.copy(),
            "last_seen": datetime.now(
                timezone.utc
            ).isoformat(),
            "received_at": time.monotonic()
        }

    return True


def get_live_status(enhed_id):
    """Henter seneste live-data for en pilledispenser."""

    result = {}

    with lock:
        devices = live_data.get(enhed_id, {})

        for device, status in devices.items():
            result[device] = {
                "data": status["data"].copy(),
                "last_seen": status["last_seen"],
                "online": (
                    time.monotonic() - status["received_at"]
                    < OFFLINE_TIMEOUT
                )
            }

    return result
