from machine import Pin
from time import sleep_ms


# Start Hall-sensoren

def hall_init(gpio=27):
    return Pin(gpio, Pin.IN, Pin.PULL_UP)


# Laes signalet

def hall_read(sensor):
    return sensor.value()


# Registrer magneten

def hall_detected(sensor):
    return hall_read(sensor) == 0


# Kontroller at signalet er stabilt

def hall_stable(sensor, delay_ms=30):
    first = hall_detected(sensor)
    sleep_ms(delay_ms)
    if hall_detected(sensor) == first:
        return first
    return None
