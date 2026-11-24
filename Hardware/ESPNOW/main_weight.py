
import json
from time import sleep_ms
from hx711_sensor import hx711_init, hx711_average, hx711_grams
from espnow_link import espnow_init, espnow_add_peer, espnow_send

COORDINATOR_MAC = "68:25:DD:EE:CA:40"

# Skal udskiftes med kalibrerede værdier
OFFSET = None
SCALE = None

link, wifi = espnow_init(6)
peer = espnow_add_peer(link, COORDINATOR_MAC)

dt, sck = hx711_init()

print("PillPilot vægtcontroller klar")

while True:
    raw = hx711_average(dt, sck, 5)

    if raw is not None:
        if OFFSET is not None and SCALE not in (None, 0):
            weight = round(hx711_grams(raw, OFFSET, SCALE), 2)
            data = {"weight_g": weight}
        else:
            data = {"raw_value": round(raw)}

        message = json.dumps({
            "type": "status",
            "device": "vægt",
            "data": data
        })

        try:
            espnow_send(link, peer, message)
            print(message)
        except OSError as error:
            print("ESP-NOW fejl:", error)

    sleep_ms(2000)
