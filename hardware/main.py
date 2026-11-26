"""PillPilot school prototype. Use supervised, non-medical test material only."""
import os
import gc
import sys
import config
import uasyncio as asyncio
from time import ticks_ms, ticks_diff
from pillpilot_api import connect_wifi
from espnow_link import espnow_init, espnow_mac
from stepper_motor import stepper_init, stepper_next, stepper_stop
from dispenser_controller import controller_init, controller_receive, controller_hall_online
from delivery_schedule import get_schedule, parse_iso
from delivery_status import set_udleveringsstatus, UDLEVERET, AFHENTET, FEJL
from armband import armband_loop, set_reminder, radio_lock, armband_command

async def wait_for_event(link, state, expected, timeout_seconds):
    start = ticks_ms()
    while ticks_diff(ticks_ms(), start) < timeout_seconds * 1000:
        controller_receive(link, state)
        while state["events"]:
            if state["events"].pop(0) == expected:
                return True
        await asyncio.sleep_ms(50)
    return False

async def update_status(ident, status, description=None):
    while True:
        try:
            async with radio_lock:
                gc.collect()
                return set_udleveringsstatus(
                    ident, status, description
                )

        except (OSError, MemoryError) as error:
            print("ERROR|API_RETRY", repr(error))
            await asyncio.sleep(5)

async def deliver(row, link, motor, state):
    ident = row["udlevering_id"]
    if not controller_receive(link, state):
        raise RuntimeError("Sensor messages are still pending")
    state["events"].clear()

    print("MOTOR|START|ID=%s" % ident)
    stepper_next(motor)
    
    print("MOTOR|STOP|ID=%s" % ident)

    if not await wait_for_event(link, state, "MEDICIN_PLACERET", 30):
        await update_status(ident, FEJL, "Placement not confirmed")
        print("ERROR|FAILED|ID=%s|Placement not confirmed" % ident)
        return False
    
    await update_status(ident, UDLEVERET)
    print("API|DELIVERED|ID=%s" % ident)

    set_reminder(True)

    try:
        if not await wait_for_event(
            link, state, "MEDICIN_AFHENTET", 3600
        ):
            print("ERROR|Pickup not confirmed")
            return False

        set_reminder(False)
        await update_status(ident, AFHENTET)
        print("API|PICKED_UP|ID=%s" % ident)

    finally:
        set_reminder(False)

    return True


async def main():
    motor = stepper_init()
    band_task = None
    try:
        wifi = connect_wifi()
        link, wifi = espnow_init(wifi)
        state = controller_init()

        gc.collect()
        print("MEMORY|FREE", gc.mem_free())

        for attempt in range(3):
            print("BLE|STARTUP_ATTEMPT", attempt + 1)

            result = await armband_command("BATTERY")

            if result is not None:
                break

            gc.collect()
            await asyncio.sleep(2)
        else:
            print("WARNING|ARMBAND_OFFLINE")

        band_task = asyncio.create_task(armband_loop())
        print("MAIN|STARTED|MAC=" + espnow_mac(wifi))
        print("MAIN|WIFI_CHANNEL=" + str(wifi.config("channel")))

        slot = 0
        last_time = None

        while True:
            controller_receive(link, state)
            state["events"].clear()
            if not wifi.isconnected():
                raise RuntimeError("WiFi disconnected")
            try:
                async with radio_lock:
                    gc.collect()
                    next_delivery, missed, due, open_deliveries, now = get_schedule()

            except (OSError, MemoryError) as error:
                print("ERROR|API_RETRY", repr(error))
                await asyncio.sleep(5)
                continue
            if last_time is not None and now < last_time:
                raise RuntimeError("Server clock moved backwards")
            last_time = now

            if missed:
                if getattr(config, "MARK_MISSED_AS_FAILED", True):
                    for row in missed:
                        ident = row["udlevering_id"]
                        await update_status(ident, FEJL, "Scheduled date has passed")
                        print("API|MISSED|ID=%s" % ident)
                raise RuntimeError("Missed deliveries: check remaining compartments")
            if open_deliveries:
                if len(open_deliveries) == 1:
                    ident = open_deliveries[0]["udlevering_id"]

                    if await wait_for_event(
                        link, state, "MEDICIN_AFHENTET", 5
                    ):
                        await update_status(ident, AFHENTET)
                        print("API|PICKED_UP|ID=%s" % ident)
                    else:
                        print("API|WAITING_FOR_PREVIOUS_PICKUP")
                else:
                    print("API|MULTIPLE_OPEN_DELIVERIES")
                    await asyncio.sleep(5)

                continue
            if next_delivery:
                print("API|NEXT|ID=%s|TIME=%s" % (next_delivery["udlevering_id"], next_delivery["planlagt_tid"]))
            if len(due) > 1:
                raise RuntimeError("Multiple overdue deliveries; manual inspection required")
            if due:
                if slot >= 8:
                    raise RuntimeError("Check wheel before starting a new filling")
                # No automatic late dose after the existing pickup deadline.
                if now >= parse_iso(due[0]["afhentningsfrist"]):
                    raise RuntimeError("Pickup deadline already passed; check delivery")
                if config.USE_HALL and slot == 0 and not controller_hall_online(state):
                    print("MOTOR|WAITING_FOR_HALL")
                elif config.USE_HALL and slot == 0 and state["hall"] is not True:
                    print("MOTOR|WAITING_FOR_HOME")
                else:
                    await deliver(due[0], link, motor, state)
                    slot += 1

            # Read incoming sensor messages while waiting for the next API poll.
            for _ in range(getattr(config, "API_INTERVAL_SECONDS", 5) * 10):
                controller_receive(link, state)
                state["events"].clear()
                await asyncio.sleep_ms(100)
    except Exception as error:
        print("ERROR|STOPPED", repr(error))
        sys.print_exception(error)
    finally:
        stepper_stop(motor)
        if band_task is not None:
            band_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("MAIN|STOPPED")
