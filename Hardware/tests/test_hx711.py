
from hx711_sensor import hx711_init, hx711_read
from time import sleep_ms


# Start sensoren
dt, sck = hx711_init()

print("HX711 klar")

while True:
    value = hx711_read(dt, sck)

    if value is None:
        print("Sensor svarer ikke")
    else:
        print("Raavaerdi:", value)

    sleep_ms(500)
