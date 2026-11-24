import json
from time import ticks_ms, ticks_diff
from espnow_link import espnow_receive
from stepper_motor import stepper_step, stepper_next, stepper_stop


# ESP-NOW MAC-adresser
HALL_MAC = "68:25:DD:E8:58:1C"
WEIGHT_MAC = "68:25:DD:E9:AF:18"

MAX_HOME_STEPS = 4400
SENSOR_TIMEOUT_MS = 3000


def controller_init():
    """Initialiserer dispenserens tilstand."""
    return {
        "hall": None,
        "hall_time": None,
        "slot": None,
        "last_id": None,

        # Vaegtsensor
        "weight_g": None,
        "weight_raw": None,
        "weight_time": None
    }


def controller_receive(link, state, timeout_ms=0):
    """Modtager beskeder fra Hall- og vaegtcontrolleren."""
    data = espnow_receive(link, timeout_ms)

    if data is None:
        return False

    sender, message = data
    sender = sender.upper()

    # HALL-CONTROLLER
    if sender == HALL_MAC:
        if message not in ("HALL|0", "HALL|1"):
            return False

        state["hall"] = message == "HALL|1"
        state["hall_time"] = ticks_ms()
        return True

    # VAEGT-CONTROLLER
    if sender == WEIGHT_MAC:
        try:
            payload = json.loads(message)

            if not isinstance(payload, dict):
                return False

            if payload.get("type") != "status":
                return False

            if payload.get("device") != "vaegt":
                return False

            values = payload.get("data")

            if not isinstance(values, dict):
                return False

            if "weight_g" in values:
                weight = values["weight_g"]

                if isinstance(weight, bool) or not isinstance(
                    weight, (int, float)
                ):
                    return False

                if not (-1000 <= weight <= 1000):
                    return False

                state["weight_g"] = weight
                state["weight_raw"] = None

            elif "raw_value" in values:
                raw = values["raw_value"]

                if isinstance(raw, bool) or not isinstance(
                    raw, (int, float)
                ):
                    return False

                state["weight_raw"] = raw
                state["weight_g"] = None

            else:
                return False

            state["weight_time"] = ticks_ms()

            return True

        except (ValueError, TypeError, KeyError):
            return False

    return False


def controller_hall_online(state):
    """Kontrollerer om Hall-controlleren er online."""
    last_time = state["hall_time"]

    if last_time is None:
        return False

    return ticks_diff(
        ticks_ms(), last_time
    ) < SENSOR_TIMEOUT_MS


def controller_weight_online(state):
    """Kontrollerer om vaegtcontrolleren er online."""
    last_time = state["weight_time"]

    if last_time is None:
        return False

    return ticks_diff(
        ticks_ms(), last_time
    ) < SENSOR_TIMEOUT_MS


def controller_home(link, motor, state):
    """Drejer dispenseren til magnetens nulpunkt."""
    state["slot"] = None

    if not controller_hall_online(state):
        print("FEJL|HALL_OFFLINE")
        return False

    if state["hall"]:
        state["slot"] = 0
        print("HOME|OK")
        return True

    try:
        for i in range(MAX_HOME_STEPS):
            stepper_step(motor, 1, 10)
            controller_receive(link, state, 0)

            if not controller_hall_online(state):
                print("FEJL|HALL_OFFLINE")
                return False

            if state["hall"]:
                state["slot"] = 0
                print("HOME|OK")
                return True

    finally:
        stepper_stop(motor)

    print("FEJL|HOME_IKKE_FUNDET")
    return False


def controller_next(motor, state, command_id):
    """Drejer til naeste medicinrum."""
    if state["slot"] is None:
        print("FEJL|FIND_HOME_FOERST")
        return False

    if not command_id or len(command_id) > 32:
        print("FEJL|UGYLDIGT_ID")
        return False

    if command_id == state["last_id"]:
        print("IGNORERET|DUBLET")
        return False

    if not controller_hall_online(state):
        print("FEJL|HALL_OFFLINE")
        return False

    stepper_next(motor, 10)

    state["slot"] = (state["slot"] + 1) % 8
    state["last_id"] = command_id

    print(
        "NEXT|UDFOERT|%s|RUM_%d" %
        (command_id, state["slot"])
    )

    return True


def controller_status(state):
    """Udskriver samlet systemstatus."""

    hall_online = controller_hall_online(state)
    weight_online = controller_weight_online(state)

    status = {
        "type": "status",
        "device": "dispenser",
        "data": {
            "slot": state["slot"],
            "hall": state["hall"],
            "hall_online": hall_online,
            "weight_online": weight_online,
            "weight_g": (
                state["weight_g"] if weight_online else None
            ),
            "weight_raw": (
                state["weight_raw"] if weight_online else None
            )
        }
    }

    print(json.dumps(status))


def controller_command(command, link, motor, state):
    """Behandler kommandoer fra Linux-serveren."""

    if command == "HOME":
        controller_home(link, motor, state)

    elif command.startswith("NEXT|"):
        controller_next(motor, state, command[5:])

    elif command == "STATUS":
        controller_status(state)

    else:
        print("FEJL|UKENDT_KOMMANDO")
