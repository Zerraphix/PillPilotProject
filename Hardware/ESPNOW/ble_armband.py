import asyncio
import bluetooth
import aioble

# Samme UUID'er som paa XIAO-armbaandet
SERVICE_UUID = bluetooth.UUID("9f8a1000-2233-4455-6677-8899aabbccdd")
COMMAND_UUID = bluetooth.UUID("9f8a1001-2233-4455-6677-8899aabbccdd")
BATTERY_UUID = bluetooth.UUID("9f8a1002-2233-4455-6677-8899aabbccdd")


# Find armbaandet via Bluetooth
async def find_armband():
    async with aioble.scan(20000, interval_us=30000,
                           window_us=30000, active=True) as scanner:
        async for result in scanner:
            if result.name() == "PillPilotBand":
                return result.device
    return None


# Send vibrationskommando eller hent batterioplysninger
async def armband_command(command):
    try:
        device = await find_armband()
        if device is None:
            print("FEJL|ARMBAND_IKKE_FUNDET")
            return

        async with await device.connect(timeout_ms=15000) as connection:
            service = await connection.service(SERVICE_UUID)
            if service is None:
                print("FEJL|BLE_SERVICE")
                return

            if command == "REMIND":
                characteristic = await service.characteristic(COMMAND_UUID)
                if characteristic is None:
                    print("FEJL|BLE_COMMAND")
                    return
                await characteristic.write(b"VIBRATE", response=True)
                print("REMIND|SENDT")

            elif command == "BATTERY":
                characteristic = await service.characteristic(BATTERY_UUID)
                if characteristic is None:
                    print("FEJL|BLE_BATTERY")
                    return
                battery = await characteristic.read()
                print("BATTERY|" + battery.decode())

    except Exception as error:
        print("FEJL|BLE|" + str(error))
