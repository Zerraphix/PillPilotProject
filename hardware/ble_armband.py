"""BLE til armbånd. Bruges foreloebigt kun ved eksplicit manuel test."""
import bluetooth
import aioble
import config

SERVICE_UUID = bluetooth.UUID(config.BLE_SERVICE_UUID)
COMMAND_UUID = bluetooth.UUID(config.BLE_COMMAND_UUID)
BATTERY_UUID = bluetooth.UUID(config.BLE_BATTERY_UUID)

connection = None
command_char = None
battery_char = None


async def find_armband():
    print("BLE|SCANNING")

    async with aioble.scan(
        10000,
        interval_us=30000,
        window_us=30000,
        active=False
    ) as scanner:
        async for result in scanner:
            if SERVICE_UUID in result.services():
                print("BLE|ARMBAND_FOUND")
                return result.device

    return None


async def disconnect_armband():
    global connection, command_char, battery_char

    command_char = None
    battery_char = None

    if connection is not None:
        if connection.is_connected():
            await connection.disconnect(timeout_ms=5000)

    connection = None


async def connect_armband():
    global connection, command_char, battery_char

    if connection is not None and connection.is_connected():
        if command_char is not None and battery_char is not None:
            return True

    await disconnect_armband()

    device = await find_armband()

    if device is None:
        print("ERROR|ARMBAND_NOT_FOUND")
        return False

    print("BLE|CONNECTING")
    connection = await device.connect(timeout_ms=15000)

    service = await connection.service(SERVICE_UUID)

    if service is None:
        raise RuntimeError("BLE service not found")

    command_char = await service.characteristic(COMMAND_UUID)
    battery_char = await service.characteristic(BATTERY_UUID)

    if command_char is None or battery_char is None:
        raise RuntimeError("BLE characteristic not found")

    print("BLE|CONNECTED")
    return True


async def armband_command(command):
    if command not in ("REMIND", "BATTERY"):
        print("ERROR|UNKNOWN_BLE_COMMAND")
        return None

    try:
        if not await connect_armband():
            return None

        if command == "REMIND":
            await command_char.write(
                b"VIBRATE",
                response=True,
                timeout_ms=5000
            )

            print("REMIND|SENT")
            return True

        if command == "BATTERY":
            battery = await battery_char.read(timeout_ms=5000)
            value = battery.decode()

            print("BATTERY|" + value)
            return value

    except Exception as error:
        print("ERROR|BLE", repr(error))

        try:
            await disconnect_armband()
        except Exception as disconnect_error:
            print("ERROR|BLE_DISCONNECT", repr(disconnect_error))

        return None