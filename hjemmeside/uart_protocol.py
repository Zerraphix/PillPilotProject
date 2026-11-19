
import json

MAX_MESSAGE_SIZE = 1024


def parse_uart_message(raw_message):
    """Modtager og validerer en JSON-besked fra UART."""

    if isinstance(raw_message, bytes):
        if len(raw_message) > MAX_MESSAGE_SIZE:
            raise ValueError("Beskeden er for stor")

        try:
            raw_message = raw_message.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Ugyldig tekstkodning")

    if not isinstance(raw_message, str):
        raise ValueError("Beskeden skal være tekst")

    if len(raw_message.encode("utf-8")) > MAX_MESSAGE_SIZE:
        raise ValueError("Beskeden er for stor")

    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        raise ValueError("Ugyldig JSON")

    if not isinstance(message, dict):
        raise ValueError("Beskeden skal være et objekt")

    if not isinstance(message.get("type"), str) or not message["type"]:
        raise ValueError("Mangler type")

    if not isinstance(message.get("device"), str) or not message["device"]:
        raise ValueError("Mangler device")

    if not isinstance(message.get("data"), dict):
        raise ValueError("Mangler data")

    return message
