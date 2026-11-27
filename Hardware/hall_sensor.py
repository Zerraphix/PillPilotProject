from machine import Pin
from time import sleep_ms


def hall_init(gpio=27):
    """Starter Hall-sensoren paa GPIO27 som standard."""
    return Pin(gpio, Pin.IN, Pin.PULL_UP)


def hall_read(sensor):
    """Laeser Hall-sensorens digitale signal."""
    return sensor.value()


def hall_detected(sensor):
    """Returnerer True, naar magneten bliver registreret."""
    return hall_read(sensor) == 0


def hall_stable(sensor, delay_ms=30):
    """Kontrollerer om magnetens signal er stabilt."""
    first = hall_detected(sensor)
    sleep_ms(delay_ms)
    second = hall_detected(sensor)

    if first == second:
        return first

    return None
