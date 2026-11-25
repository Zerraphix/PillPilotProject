"""Receive Hall status and weight events from the configured ESP32s."""
import json
import config
from stepper_motor import stepper_step, stepper_stop
from time import ticks_ms, ticks_diff, sleep_ms
from espnow_link import espnow_receive


def controller_init():
    return {"hall": None, "hall_time": None, "events": []}


def controller_receive(link, state):
    for _ in range(32):
        packet = espnow_receive(link, 0)
        if packet is None:
            return True
        sender, message = packet
        if sender == config.HALL_MAC.strip().upper():
            if message in ("HALL|0", "HALL|1"):
                state["hall"] = message == "HALL|1"
                state["hall_time"] = ticks_ms()
        elif sender == config.VAEGT_MAC.strip().upper():
            try:
                obj = json.loads(message)
                if obj["type"] != "event" or obj["device"] != "vaegt":
                    continue
                event = obj["data"]["event"]
                weight = obj["data"]["weight_g"]
                if event not in ("MEDICIN_PLACERET", "MEDICIN_AFHENTET"):
                    continue
                if type(weight) not in (int, float) or not -float("inf") < weight < float("inf"):
                    continue
                if event == "MEDICIN_PLACERET" and weight <= 0:
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            if len(state["events"]) >= 16:
                raise RuntimeError("Weight event queue is full")
            state["events"].append(event)
            print("WEIGHT|%s|%s g" % (
                "PLACED" if event == "MEDICIN_PLACERET" else "PICKED_UP", weight))
    return False


def controller_hall_online(state):
    return (state["hall_time"] is not None
            and ticks_diff(ticks_ms(), state["hall_time"]) < 3000)

def controller_home(link, motor, state):
    print("HOME|SEARCHING")

    try:
        start = ticks_ms()

        while not controller_hall_online(state):
            controller_receive(link, state)

            if ticks_diff(ticks_ms(), start) >= 3000:
                print("HOME|HALL_OFFLINE")
                return False

            sleep_ms(20)

        for _ in range(4400):
            controller_receive(link, state)

            if not controller_hall_online(state):
                print("HOME|HALL_OFFLINE")
                return False

            if state["hall"] is True:
                print("HOME|OK")
                return True

            stepper_step(motor, 1, 2)

        print("HOME|NOT_FOUND")
        return False

    finally:
        stepper_stop(motor)
