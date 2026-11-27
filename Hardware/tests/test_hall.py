from machine import Pin
from time import sleep

sensor = Pin(27, Pin.IN, Pin.PULL_UP)

while True:
    print("Hall GPIO27:", sensor.value())
    sleep(0.5)