"""Main ESP32: API-planlaegning, ESP-NOW og BLE/UART-status.
Ingen automatisk motorbevægelse eller medicinudlevering.
"""
from time import ticks_ms, ticks_diff
import config
import uasyncio as asyncio
from pillpilot_api import connect_wifi
from delivery_schedule import schedule_init, schedule_poll
from espnow_link import espnow_init, espnow_mac
from dispenser_controller import controller_init, controller_receive, controller_command
from stepper_motor import stepper_init, stepper_stop
from armband import armband_command, armband_loop

API_INTERVAL_MS = getattr(config, "API_INTERVAL_SECONDS", 60) * 1000


def create_system():
    wifi = connect_wifi()
    link, wifi = espnow_init(wifi)
    motor = stepper_init()
    state = controller_init()
    print("MAIN|STARTET|MAC=" + espnow_mac(wifi))
    try:
        print("MAIN|WIFI_KANAL=" + str(wifi.config("channel")))
    except Exception:
        pass
    return {"wifi": wifi, "link": link, "motor": motor, "state": state,
            "schedule": schedule_init()}


def poll_sensors(system, maximum=30):
    for _ in range(maximum):
        if not controller_receive(system["link"], system["state"], 0):
            break


def show_next_delivery(system=None):
    return schedule_poll(system["schedule"] if system is not None else schedule_init())


def command(system, text):
    """Manuel REPL-test efter stop af hovedloekken, kun med tom dispenser."""
    if text in ("REMIND", "BATTERY"):
        return asyncio.run(armband_command(text))
    if text == "API":
        return show_next_delivery(system)
    return controller_command(text, system["link"], system["motor"], system["state"])


async def _loop(system):
    last_api = None
    band_task = asyncio.create_task(armband_loop())
    try:
        while True:
            poll_sensors(system)
            if last_api is None or ticks_diff(ticks_ms(), last_api) >= API_INTERVAL_MS:
                if system["wifi"].isconnected():
                    show_next_delivery(system)
                else:
                    system["schedule"].update({"ready": False, "next": None, "due": [], "missed": []})
                    print("FEJL|WIFI_OFFLINE")
                last_api = ticks_ms()
            await asyncio.sleep_ms(50)
    finally:
        band_task.cancel()
        stepper_stop(system["motor"])
        try:
            await band_task
        except asyncio.CancelledError:
            pass


def loop(system):
    asyncio.run(_loop(system))


def main():
    system = create_system()
    try:
        loop(system)
    except KeyboardInterrupt:
        print("MAIN|STOPPET")


if __name__ == "__main__":
    main()
