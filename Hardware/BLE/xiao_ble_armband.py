import asyncio
import bluetooth
import aioble
import network
from machine import Pin, ADC


network.WLAN(network.STA_IF).active(False)
network.WLAN(network.AP_IF).active(False)

motor = Pin(2, Pin.OUT, value=0)
battery_adc = ADC(Pin(0))
battery_adc.atten(ADC.ATTN_11DB)

SERVICE_UUID = bluetooth.UUID("9f8a1000-2233-4455-6677-8899aabbccdd")
COMMAND_UUID = bluetooth.UUID("9f8a1001-2233-4455-6677-8899aabbccdd")
BATTERY_UUID = bluetooth.UUID("9f8a1002-2233-4455-6677-8899aabbccdd")

service = aioble.Service(SERVICE_UUID)
command = aioble.Characteristic(service, COMMAND_UUID, write=True, capture=True)
battery_info = aioble.Characteristic(service, BATTERY_UUID, read=True)
aioble.register_services(service)


def read_battery_voltage():
    """Maaler batteriets spaending i volt via D0."""
    total = 0
    for i in range(16):
        total += battery_adc.read_uv()

    voltage = total / 16 / 1000000
    return voltage * 2


def get_battery_percent(voltage):
    """Beregner et omtrentligt batteriniveau i procent."""
    percent = round((voltage - 3.0) / 1.2 * 100)
    percent = max(0, min(100, percent))
    return percent


def update_battery():
    """Opdaterer batteriprocent og volt, som controlleren kan laese."""
    voltage = read_battery_voltage()
    percent = get_battery_percent(voltage)
    battery_text = "{}% | {:.2f} V".format(percent, voltage)

    battery_info.write(battery_text.encode())
    print("Battery:", battery_text)


async def vibrate():
    """Aktiverer vibrationsmotoren to gange."""
    try:
        for i in range(2):
            motor.on()
            await asyncio.sleep_ms(300)
            motor.off()
            await asyncio.sleep_ms(200)
    finally:
        motor.off()


async def battery_loop():
    """Opdaterer batteriet hvert minut."""
    while True:
        await asyncio.sleep(60)
        update_battery()


async def bluetooth_loop():
    """Venter paa Bluetooth-kommandoer og starter igen ved afbrydelse."""
    while True:
        print("Waiting for controller...")

        try:
            connection = await aioble.advertise(
                250000,
                name="PillPilotBand",
                services=[SERVICE_UUID]
            )

            async with connection:
                print("Bluetooth connected")

                while connection.is_connected():
                    try:
                        sender, message = await command.written(timeout_ms=1000)
                    except asyncio.TimeoutError:
                        continue

                    if sender != connection:
                        continue

                    if message == b"VIBRATE":
                        await vibrate()
                    elif message == b"TEST":
                        update_battery()
                        await vibrate()
                    elif message == b"BATTERY":
                        update_battery()

        except Exception as error:
            print("Bluetooth error:", error)
            await asyncio.sleep(2)
        finally:
            motor.off()


async def main():
    """Starter batterimaaling og Bluetooth paa armbaandet."""
    update_battery()
    asyncio.create_task(battery_loop())
    await bluetooth_loop()


try:
    asyncio.run(main())
finally:
    motor.off()
