import asyncio
import bluetooth
import aioble
import network
from machine import Pin, ADC

# PillPilot armband - XIAO ESP32-C6
# D0: batterispaending via 100k + 100k spaendingsdeler
# D2: vibration via 330 ohm og BC547C

# Sluk Wi-Fi. Armbandet bruger kun Bluetooth.
network.WLAN(network.STA_IF).active(False)
network.WLAN(network.AP_IF).active(False)

motor = Pin(2, Pin.OUT, value=0)
battery_adc = ADC(Pin(0))
battery_adc.atten(ADC.ATTN_11DB)

SERVICE_UUID = bluetooth.UUID('9f8a1000-2233-4455-6677-8899aabbccdd')
COMMAND_UUID = bluetooth.UUID('9f8a1001-2233-4455-6677-8899aabbccdd')
BATTERY_UUID = bluetooth.UUID('9f8a1002-2233-4455-6677-8899aabbccdd')

service = aioble.Service(SERVICE_UUID)
command = aioble.Characteristic(service, COMMAND_UUID, write=True, capture=True)
battery_info = aioble.Characteristic(service, BATTERY_UUID, read=True)
aioble.register_services(service)


def read_battery_voltage():
    # 16 ADC-maalinger giver en roligere vaerdi.
    total = 0
    for _ in range(16):
        total += battery_adc.read_uv()
    return (total / 16) / 1000000 * 2


def get_battery_percent(voltage):
    # Simpelt estimat. Ikke en praecis batterimaaler.
    percent = round((voltage - 3.0) / 1.2 * 100)
    return max(0, min(100, percent))


def update_battery():
    voltage = read_battery_voltage()
    percent = get_battery_percent(voltage)
    text = '{}% | {:.2f} V'.format(percent, voltage)
    battery_info.write(text.encode())
    print('Battery:', text)


async def vibrate():
    # To korte vibrationer.
    try:
        for _ in range(2):
            motor.on()
            await asyncio.sleep_ms(300)
            motor.off()
            await asyncio.sleep_ms(200)
    finally:
        motor.off()


async def battery_loop():
    while True:
        await asyncio.sleep(60)
        update_battery()


async def bluetooth_loop():
    while True:
        print('Waiting for controller...')
        try:
            # 250 ms er den indstilling, vi har testet virker.
            connection = await aioble.advertise(
                250000,
                name='PillPilotBand',
                services=[SERVICE_UUID],
            )

            async with connection:
                print('Bluetooth connected')
                while connection.is_connected():
                    try:
                        sender, message = await command.written(timeout_ms=1000)
                    except asyncio.TimeoutError:
                        continue

                    if sender != connection:
                        continue

                    if message == b'VIBRATE':
                        await vibrate()
                    elif message == b'TEST':
                        update_battery()
                        await vibrate()
                    elif message == b'BATTERY':
                        update_battery()

        except Exception as error:
            print('Bluetooth error:', error)
            await asyncio.sleep(2)
        finally:
            motor.off()


async def main():
    update_battery()
    asyncio.create_task(battery_loop())
    await bluetooth_loop()


try:
    asyncio.run(main())
finally:
    motor.off()

