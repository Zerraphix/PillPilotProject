from time import ticks_ms, ticks_diff
from espnow_link import espnow_receive
from stepper_motor import stepper_step, stepper_next, stepper_stop


HALL_MAC = "68:25:DD:E8:58:1C"
MAX_HOME_STEPS = 4400


def controller_init():
    """Opretter controllerens oplysninger om sensor og medicinrum."""
    return {"hall": None, "hall_time": None, "slot": None, "last_id": None}


def controller_receive(link, state, timeout_ms=0):
    """Modtager Hall-sensorens magnetstatus via ESP-NOW."""
    data = espnow_receive(link, timeout_ms)
    if data is None:
        return False

    sender, message = data
    if sender.upper() != HALL_MAC:
        return False

    if message != "HALL|0" and message != "HALL|1":
        return False

    state["hall"] = message == "HALL|1"
    state["hall_time"] = ticks_ms()
    return True


def controller_hall_online(state):
    """Kontrollerer om Hall-sensoren har svaret for nylig."""
    last_time = state["hall_time"]
    if last_time is None:
        return False

    return ticks_diff(ticks_ms(), last_time) < 3000


def controller_home(link, motor, state):
    """Drejer dispenseren frem til magnetens nulpunkt."""
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
    """Drejer til naeste medicinrum, hvis kommandoen er gyldig."""
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

    print("NEXT|UDFOERT|%s|RUM_%d" % (command_id, state["slot"]))
    return True


def controller_command(command, link, motor, state):
    """Udfoerer HOME, NEXT og STATUS fra Linux-serveren."""
    if command == "HOME":
        controller_home(link, motor, state)
    elif command.startswith("NEXT|"):
        controller_next(motor, state, command[5:])
    elif command == "STATUS":
        print("STATUS|RUM=%s|HALL=%s|ONLINE=%s" % (
            state["slot"], state["hall"], controller_hall_online(state)
        ))
    else:
        print("FEJL|UKENDT_KOMMANDO")
