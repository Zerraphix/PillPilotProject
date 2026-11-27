from machine import Pin, disable_irq, enable_irq
from time import sleep_us, ticks_us, ticks_diff


def hx711_init():
    """Starter HX711 med data paa GPIO25 og clock paa GPIO26."""
    dt = Pin(25, Pin.IN)
    sck = Pin(26, Pin.OUT, value=0)
    return dt, sck


def hx711_read(dt, sck):
    """Laeser en 24-bit raavaerdi fra HX711."""
    start = ticks_us()

    while dt.value() == 1:
        if ticks_diff(ticks_us(), start) > 1000000:
            return None

    value = 0
    state = disable_irq()

    try:
        for i in range(24):
            sck.value(1)
            sleep_us(1)
            value = (value << 1) | dt.value()
            sck.value(0)
            sleep_us(1)

        sck.value(1)
        sleep_us(1)
        sck.value(0)
    finally:
        enable_irq(state)

    if value & 0x800000:
        value -= 0x1000000

    return value


def hx711_average(dt, sck, measurements=10):
    """Beregner gennemsnittet af flere HX711-maalinger."""
    total = 0

    for i in range(measurements):
        value = hx711_read(dt, sck)
        if value is None:
            return None

        total += value

    return total / measurements


def hx711_tare(dt, sck):
    """Maaler nulpunktet, naar vaegten er uden belastning."""
    return hx711_average(dt, sck)


def hx711_grams(value, offset, scale):
    """Omregner en raavaerdi til gram efter kalibrering."""
    if value is None or scale == 0:
        return None

    return (value - offset) / scale
