"""BLE til armbånd. Bruges foreloebigt kun ved eksplicit manuel test."""
import bluetooth
import aioble
import config

SERVICE_UUID = bluetooth.UUID(config.BLE_SERVICE_UUID)
COMMAND_UUID = bluetooth.UUID(config.BLE_COMMAND_UUID)
BATTERY_UUID = bluetooth.UUID(config.BLE_BATTERY_UUID)


async def find_armband():
    """Finder kun den enhed, der annoncerer navnet fra config.py."""
    async with aioble.scan(
        getattr(config, "BLE_SCAN_MS", 20000),
        interval_us=30000, window_us=30000, active=True
    ) as scanner:
        async for result in scanner:
            if result.name() == config.BLE_DEVICE_NAME:
                return result.device
    return None


async def armband_command(command):
    """REMIND sender vibration, BATTERY læser batteristatus."""
    if command not in ("REMIND", "BATTERY"):
        print("FEJL|UKENDT_BLE_KOMMANDO")
        return None
    try:
        device = await find_armband()
        if device is None:
            print("FEJL|ARMBAND_IKKE_FUNDET")
            return None

        async with await device.connect(timeout_ms=15000) as connection:
            service = await connection.service(SERVICE_UUID)
            if service is None:
                print("FEJL|BLE_SERVICE")
                return None

            if command == "REMIND":
                characteristic = await service.characteristic(COMMAND_UUID)
                if characteristic is None:
                    print("FEJL|BLE_COMMAND")
                    return None
                await characteristic.write(b"VIBRATE", response=True)
                print("REMIND|SENDT")
                return True

            characteristic = await service.characteristic(BATTERY_UUID)
            if characteristic is None:
                print("FEJL|BLE_BATTERY")
                return None
            battery = await characteristic.read()
            value = battery.decode()
            print("BATTERY|" + value)
            return value
    except Exception as error:
        print("FEJL|BLE|" + str(error))
        return None
