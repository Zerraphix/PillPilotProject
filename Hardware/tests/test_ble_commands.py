import asyncio
from ble_armband import armband_command


async def main():
    print("Tester vibration ...")
    await armband_command("REMIND")
    await asyncio.sleep(1)
    print("Laeser batteri ...")
    await armband_command("BATTERY")


asyncio.run(main())
