from time import ticks_ms, ticks_diff
from espnow_link import espnow_receive
from stepper_motor import stepper_step, stepper_next, stepper_stop

# ESP32 med Hall-sensor
HALL_MAC = "68:25:DD:E8:58:1C"

# Maksimalt en omgang for at finde magneten
MAX_HOME_STEPS = 4400


# Start styringen

def controller_init():
    return {"hall": None, "hall_time": None, "slot": None, "last_id": None}


# Modtag Hall-sensorens status

def controller_receive(link, state, timeout_ms=0):
    data = espnow_receive(link, timeout_ms)
    if data:
        sender, message = data
        if sender.upper() == HALL_MAC and message in ("HALL|0", "HALL|1"):
            state["hall"] = message == "HALL|1"
            state["hall_time"] = ticks_ms()
            return True
    return False


# Tjek om Hall-sensoren svarer

def controller_hall_online(state):
    stamp = state["hall_time"]
    return stamp is not None and ticks_diff(ticks_ms(), stamp) < 3000


# Find karussellens startposition

def controller_home(link, motor, state):
    state["slot"] = None
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


# Drej til naeste rum efter en godkendt kommando

def controller_next(motor, state, command_id):
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


# Haandter kommando fra Linux-serveren

def controller_command(command, link, motor, state):
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
