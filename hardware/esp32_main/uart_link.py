"""JSON-lines til eksisterende UART-reader paa Raspberry Pi (USB/REPL)."""
import json
import config


def send_armband_status(battery_pct):
    """Kald kun efter frisk BLE-aflaesning, aldrig ved offline armbånd.

    USB-UART-broen giver normalt ikke ESP32 besked om vaerten lytter.
    UART_LIVE_ENABLED er derfor en eksplicit indstilling, ikke autodetektion.
    """
    if not getattr(config, "UART_LIVE_ENABLED", False):
        return False
    enhed_id = getattr(config, "ENHED_ID", "")
    if not enhed_id or type(battery_pct) is not int or not 0 <= battery_pct <= 100:
        return False
    print(json.dumps({"type": "status", "enhed_id": enhed_id,
                      "device": "armbaand", "data": {"battery_pct": battery_pct}}))
    return True
