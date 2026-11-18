
from hx711_sensor import hx711_init, hx711_tare
from hx711_sensor import hx711_average, hx711_grams
from time import sleep_ms

# Kendt vaegt i gram
KNOWN_WEIGHT = 100

# Start HX711
dt, sck = hx711_init()

# Find nulpunkt
print("Fjern al vaegt fra sensoren")
sleep_ms(5000)

offset = hx711_tare(dt, sck)

if offset is None:
    raise RuntimeError("HX711 svarer ikke")

print("Nulpunkt:", offset)

# Kalibrer med kendt vaegt
print("Placer", KNOWN_WEIGHT, "gram paa sensoren")
sleep_ms(5000)

loaded = hx711_average(dt, sck)

if loaded is None:
    raise RuntimeError("HX711 svarer ikke")

scale = (loaded - offset) / KNOWN_WEIGHT

if abs(scale) < 0.001:
    raise RuntimeError("Ingen vaegtændring registreret")

print("Kalibreringsfaktor:", scale)

# Vis vaegten i gram
print("Maaling starter")

while True:
    value = hx711_average(dt, sck, 5)
    grams = hx711_grams(value, offset, scale)

    if grams is None:
        print("Maaling fejlede")
    else:
        print("Vaegt: {:.2f} g".format(grams))

    sleep_ms(500)
