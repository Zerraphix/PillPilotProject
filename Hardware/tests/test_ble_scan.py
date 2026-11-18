import asyncio
import aioble

async def main():
    print("Soger efter Bluetooth-enheder ...")

    async with aioble.scan(
        20000,
        interval_us=30000,
        window_us=30000,
        active=True
    ) as scanner:

        async for device in scanner:
            print("Navn:", device.name())
            print("Adresse:", device.device)
            print("Signal:", device.rssi)
            print("-------------------")

    print("Scanning afsluttet")

asyncio.run(main())
