# PillPilot - Test af armband fra controller ESP32
import asyncio
import bluetooth
import aioble

SERVICE_UUID = bluetooth.UUID("9f8a1000-2233-4455-6677-8899aabbccdd")
COMMAND_UUID = bluetooth.UUID("9f8a1001-2233-4455-6677-8899aabbccdd")
BATTERY_UUID = bluetooth.UUID("9f8a1002-2233-4455-6677-8899aabbccdd")


async def main():
    print("Soger efter PillPilotBand ...")
    armband = None

    # Find armbandet
    async with aioble.scan(
        20000, interval_us=30000, window_us=30000, active=True
    ) as scanner:
        async for device in scanner:
            if device.name() == "PillPilotBand":
                armband = device.device
                break

    if armband is None:
        print("Armbaandet blev ikke fundet")
        return

    # Opret forbindelse
    async with await armband.connect() as connection:
        service = await connection.service(SERVICE_UUID)
        if service is None:
            print("Bluetooth-service mangler")
            return

        command = await service.characteristic(COMMAND_UUID)
        battery = await service.characteristic(BATTERY_UUID)

        if command is None or battery is None:
            print("Bluetooth-funktion mangler")
            return

        # Bed armbaandet maale batteriet og vibrere
        print("Sender TEST ...")
        await command.write(b"TEST", response=True)
        await asyncio.sleep(1.5)

        # Vis batteriinformation fra armbaandet
        info = await battery.read()
        print("Batteri:", info.decode())
        print("TEST sendt - kontroller at motoren vibrerede to gange")


asyncio.run(main())
