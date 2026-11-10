from machine import Pin
from time import sleep_ms

def hall_init(gpio=32):
    return Pin(gpio, Pin.IN, Pin.PULL_UP)

def hall_read(sensor):
    return sensor.value(
    )
def hall_detected(sensor):
    return sensor.value() == 0

def hall_debounce(sensor, delay=50):
    if hall_detected(sensor):
        return False

    sleep_ms(delay)
    return hall_detected(sensor)
def hall_status(sensor):
    return {
        "signal" : hall_read(sensor),
        "magnetic_field_detected" : hall_detected(sensor)
    }