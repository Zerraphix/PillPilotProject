import gc
import esp32
import uasyncio as asyncio

from pillpilot_api import connect_wifi
from armband import armband_command
from delivery_schedule import get_schedule


def memory():
    gc.collect()
    print("MEMORY|FREE", gc.mem_free())
    print("MEMORY|IDF", esp32.idf_heap_info(esp32.HEAP_DATA))


async def test():
    connect_wifi()

    print("TEST 1|BEFORE API")
    memory()
    await armband_command("BATTERY")

    await asyncio.sleep(5)

    print("TEST 2|API REQUESTS")

    for i in range(6):
        schedule = get_schedule()
        print("API|OK", i + 1)
        await asyncio.sleep(5)

    print("TEST 3|AFTER API")
    memory()
    await armband_command("BATTERY")

    print("TEST 4|AFTER GC")
    schedule = None
    gc.collect()
    memory()
    await armband_command("BATTERY")


asyncio.run(test())