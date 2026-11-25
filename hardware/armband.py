"""Send bracelet reminders and live battery status."""
import config
import gc
import uasyncio as asyncio
from time import ticks_ms, ticks_diff
from uart_link import send_armband_status

radio_lock = asyncio.Lock()

reminder_active = False
last_reminder = None


def set_reminder(active):
    global reminder_active, last_reminder
    if reminder_active != active:
        reminder_active = active
        last_reminder = None


async def armband_command(command):
    # Do not overlap BLE operations with HTTP requests.
    async with radio_lock:
        try:
            from ble_armband import armband_command as ble_command
            result = await ble_command(command)
            if command == "BATTERY" and result is not None:
                value = int(result.split("%", 1)[0].strip())
                if not 0 <= value <= 100:
                    raise ValueError("Battery percentage out of range")
                send_armband_status(value)
                return value
            return result
        except Exception as error:
            print("ERROR|ARMBAND", repr(error))
            return None
        finally:
            gc.collect()


async def armband_loop():
    global last_reminder
    last_battery = ticks_ms()
    battery_interval = getattr(config, "ARMBAND_INTERVAL_SECONDS", 30) * 1000

    while True:
        now = ticks_ms()
        if reminder_active and (last_reminder is None or
                                ticks_diff(now, last_reminder) >= 60000):
            last_reminder = now
            await armband_command("REMIND")
        elif getattr(config, "UART_LIVE_ENABLED", False) and (
                last_battery is None or
                ticks_diff(now, last_battery) >= battery_interval):
            last_battery = now
            await armband_command("BATTERY")

        await asyncio.sleep(1)
