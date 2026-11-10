from machine import Pin
from time import sleep_ms

# Initialiser sensoren
def hall_init(gpio=32):
    return Pin(gpio, Pin.IN, Pin.PULL_UP)

# Læs sensoren
def hall_read(sensor):
    return sensor.value(
    )

# Tjek om der er et magnetfelt til stede
def hall_detected(sensor):
    return sensor.value() == 0


# Bekræft magnetregistrering
def hall_debounce(sensor, delay=50):
    if hall_detected(sensor):
        return False

    sleep_ms(delay)
    return hall_detected(sensor)

# Hent sensorens status
def hall_status(sensor):
    return {
        "signal" : hall_read(sensor),
        "magnetic_field_detected" : hall_detected(sensor)
    }