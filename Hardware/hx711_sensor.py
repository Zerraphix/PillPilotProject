
from machine import Pin, disable_irq, enable_irq
from time import sleep_us, ticks_us, ticks_diff


# Start HX711
def hx711_init():
    dt = Pin(25, Pin.IN)
    sck = Pin(26, Pin.OUT, value=0)

    return dt, sck


# Laes vaegtens raavaerdi
def hx711_read(dt, sck):
    start = ticks_us()

    # Vent paa at sensoren er klar
    while dt.value() == 1:
        if ticks_diff(ticks_us(), start) > 1000000:
            return None

    value = 0

    # Laes 24 bit fra sensoren
    state = disable_irq()

    try:
        for i in range(24):
            sck.value(1)
            sleep_us(1)

            value = (value << 1) | dt.value()

            sck.value(0)
            sleep_us(1)

        # Vaelg kanal A
        sck.value(1)
        sleep_us(1)
        sck.value(0)

    finally:
        enable_irq(state)

    # Konverter negativ vaerdi
    if value & 0x800000:
        value -= 0x1000000

    return value


# Beregn gennemsnit
def hx711_average(dt, sck, measurements=10):
    total = 0

    for i in range(measurements):
        value = hx711_read(dt, sck)

        if value is None:
            return None

        total += value

    return total / measurements


# Nulstil vaegten
def hx711_tare(dt, sck):
    return hx711_average(dt, sck)


# Konverter til gram
def hx711_grams(value, offset, scale):
    if value is None or scale == 0:
        return None

    return (value - offset) / scale
