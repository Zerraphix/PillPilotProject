
from machine import Pin
from time import sleep

# Vibrationsmotor styres via BC547C
# XIAO D2 (GPIO2) -> 330 ohm -> Base

motor = Pin(2, Pin.OUT, value=0)

print("PillPilot - vibrationstest startet")

while True:
    print("Vibration TIL")
    motor.value(1)
    sleep(1)

    print("Vibration FRA")
    motor.value(0)
    sleep(2)
