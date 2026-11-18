
from machine import Pin, ADC
from time import sleep

# PillPilot - Batteriovervaagning
# XIAO ESP32-C6
# D0 = GPIO0 (batterimaaling)

battery_adc = ADC(Pin(0))
battery_adc.atten(ADC.ATTN_11DB)

# Spaendingsdeler: 100k + 100k
VOLTAGE_DIVIDER = 2.0

# Foreloebige batterigraenser
BATTERY_MIN = 3.0
BATTERY_MAX = 4.2

# Maal hvert 10. sekund
INTERVAL = 10

# Gem de seneste 30 maalinger (5 minutter)
MAX_SAMPLES = 30

# Minimum spaendingsaendring paa 30 mV
THRESHOLD = 0.03

history = []


# Laes batterispaending
def read_battery_voltage():
    total = 0

    for _ in range(20):
        total += battery_adc.read_uv()
        sleep(0.01)

    adc_voltage = total / 20 / 1000000

    return adc_voltage * VOLTAGE_DIVIDER


# Beregn batteriprocent
def battery_percent(voltage):
    percent = (
        (voltage - BATTERY_MIN)
        / (BATTERY_MAX - BATTERY_MIN)
    ) * 100

    return round(max(0, min(100, percent)))


# Find udviklingen i batterispaending
def battery_trend():
    if len(history) < MAX_SAMPLES:
        return "Indsamler maalinger"

    # Sammenlign de foerste og sidste 5 maalinger
    first = sum(history[:5]) / 5
    last = sum(history[-5:]) / 5

    difference = last - first

    if difference > THRESHOLD:
        return "Sandsynligvis oplader"

    if difference < -THRESHOLD:
        return "Sandsynligvis aflader"

    return "Stabil / ukendt"


# Vis batteristatus
def show_battery_status():
    voltage = read_battery_voltage()
    percent = battery_percent(voltage)

    history.append(voltage)

    if len(history) > MAX_SAMPLES:
        history.pop(0)

    status = battery_trend()

    print("-----------------------------")
    print("PillPilot - Batteristatus")
    print("Spaending: {:.3f} V".format(voltage))
    print("Batteri: {} %".format(percent))
    print("Status:", status)

    if voltage < 3.3:
        print("ADVARSEL: Lav batterispaending")


# Start
print("PillPilot batteriovervaagning startet")

while True:
    show_battery_status()
    sleep(INTERVAL)
