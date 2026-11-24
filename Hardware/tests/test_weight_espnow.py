import json
import time

from espnow_link import (
    espnow_init,
    espnow_add_peer,
    espnow_send
)

CONTROLLER_MAC = "68:25:DD:EE:CA:40"

link, wifi = espnow_init(10)
peer = espnow_add_peer(link, CONTROLLER_MAC)

print("PillPilot ESP-NOW vaegttest startet")

counter = 0

while True:
    counter += 1

    message = {
        "type": "status",
        "device": "vaegt",
        "data": {
            "weight_g": 125.5,
            "counter": counter
        }
    }

    payload = json.dumps(message)

    try:
        sent = espnow_send(link, peer, payload)

        if sent:
            print("SENDT:", payload)
        else:
            print("FEJL: ESP-NOW levering ikke bekraeftet")

    except OSError as error:
        print("ESP-NOW fejl:", error)

    time.sleep(2)