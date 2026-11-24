"""Armbandets service: BLE-laesning og valgfri UART-status."""
import config
from uart_link import send_armband_status


async def armband_command(command):
    try:
        from ble_armband import armband_command as ble_command
        result = await ble_command(command)
        if command == "BATTERY" and result is not None:
            # Eksisterende BLE-protokol returnerer procent som tekst.
            value = int(result.strip())
            if not 0 <= value <= 100:
                raise ValueError("Batteriprocent uden for interval")
            send_armband_status(value)
            return value
        return result
    except Exception as error:
        print("FEJL|ARMBAND|" + str(error))
        return None


async def armband_loop():
    import uasyncio as asyncio
    while True:
        if getattr(config, "UART_LIVE_ENABLED", False):
            # Ingen JSON ved offline armbånd eller ugyldig maaling.
            await armband_command("BATTERY")
        await asyncio.sleep(getattr(config, "ARMBAND_INTERVAL_SECONDS", 30))
