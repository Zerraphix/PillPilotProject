"""Modtager sensorsvar og styrer homing og motorens rummarkering.

Motorbevaegelse betyder IKKE, at medicin er fysisk udleveret.
"""
from time import ticks_ms, ticks_diff
import config
from espnow_link import espnow_receive
from stepper_motor import stepper_step, stepper_next, stepper_stop

HALL_MAC = config.HALL_MAC.strip().upper()
IR_MAC = getattr(config, "IR_MAC", "").strip().upper()
VAEGT_MAC = getattr(config, "VAEGT_MAC", "").strip().upper()
MAX_HOME_STEPS = 4400
HALL_TIMEOUT_MS = 3000


def controller_init():
    return {
        "hall": None,
        "hall_time": None,
        "slot": None,
        "last_id": None,
        "sensors": {},  # Andre sensorer: kun modtaget tekst, ikke bevis for udlevering.
    }


def controller_receive(link, state, timeout_ms=0):
    """Laeser een ESP-NOW-besked. Kun konfigurerede MAC-adresser accepteres."""
    packet = espnow_receive(link, timeout_ms)
    if packet is None:
        return False

    sender, message = packet
    if HALL_MAC and sender == HALL_MAC:
        if message == "HALL|0" or message == "HALL|1":
            state["hall"] = message == "HALL|1"
            state["hall_time"] = ticks_ms()
    elif IR_MAC and sender == IR_MAC:
        state["sensors"]["ir"] = {"raw": message, "time": ticks_ms()}
    elif VAEGT_MAC and sender == VAEGT_MAC:
        previous = state["sensors"].get("vaegt")
        state["sensors"]["vaegt"] = {"raw": message, "time": ticks_ms()}
        if previous is None or previous["raw"] != message:
            print("SENSOR|vaegt|" + message)
    # Ukendte afsendere og ukendte Hall-beskeder ignoreres.
    return True


def controller_hall_online(state):
    last_time = state["hall_time"]
    return last_time is not None and ticks_diff(ticks_ms(), last_time) < HALL_TIMEOUT_MS


def controller_home(link, motor, state):
    """Finder magneten. Kræver, at Hall-enheden sender status løbende."""
    state["slot"] = None
    for _ in range(10):
        if not controller_receive(link, state, 0):
            break

    if not controller_hall_online(state):
        print("FEJL|HALL_OFFLINE")
        return False

    if state["hall"]:
        state["slot"] = 0
        print("HOME|OK")
        return True

    try:
        for _ in range(MAX_HOME_STEPS):
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


def controller_next(motor, state, command_id, link=None):
    """Bevaeger et rum med dubletkontrol og kontrol af Hall-forbindelsen."""
    old_slot = state["slot"]
    if old_slot is None:
        print("FEJL|FIND_HOME_FOERST")
        return False
    if not isinstance(command_id, str) or not command_id or len(command_id) > 32:
        print("FEJL|UGYLDIGT_ID")
        return False
    if command_id == state["last_id"]:
        print("IGNORERET|DUBLET")
        return False
    if not controller_hall_online(state):
        print("FEJL|HALL_OFFLINE")
        return False

    # Ved afbrudt bevaegelse kender vi ikke laengere positionen.
    state["slot"] = None

    def check_sensor(step_index):
        if link is not None and step_index % 8 == 0:
            for _ in range(4):
                if not controller_receive(link, state, 0):
                    break
        return controller_hall_online(state)

    try:
        moved = stepper_next(motor, 10, on_step=check_sensor)
    except Exception:
        print("FEJL|MOTOR_AFBROEDT|HOME_KRAEVES")
        raise

    if not moved:
        print("FEJL|HALL_OFFLINE_UNDER_KOERSEL|HOME_KRAEVES")
        return False

    state["slot"] = (old_slot + 1) % 8
    state["last_id"] = command_id
    print("NEXT|UDFOERT|%s|RUM_%d" % (command_id, state["slot"]))
    return True


def controller_status(state):
    text = "STATUS|RUM=%s|HALL=%s|ONLINE=%s" % (
        state["slot"], state["hall"], controller_hall_online(state)
    )
    print(text)
    for name, item in state["sensors"].items():
        print("SENSOR|%s|%s" % (name, item["raw"]))
    return text


def controller_command(command, link, motor, state):
    command = command.strip()
    if command == "HOME":
        return controller_home(link, motor, state)
    if command.startswith("NEXT|"):
        return controller_next(motor, state, command[5:], link=link)
    if command == "STATUS":
        return controller_status(state)
    print("FEJL|UKENDT_KOMMANDO")
    return False
