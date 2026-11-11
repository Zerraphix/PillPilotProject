from time import sleep_ms, ticks_ms, ticks_diff
from hall_sensor import hall_init, hall_stable
from espnow_link import espnow_init, espnow_add_peer, espnow_send

# Motorens ESP32
COORDINATOR_MAC = "68:25:DD:EE:CA:40"

link, wifi = espnow_init(6)
peer = espnow_add_peer(link, COORDINATOR_MAC)
hall = hall_init(27)

last_sent = None
last_time = ticks_ms()

print("Hall-sensor klar")

while True:
    status = hall_stable(hall, 30)

    # Send ved aendring og hvert halve sekund
    if status is not None:
        if status != last_sent or ticks_diff(ticks_ms(), last_time) >= 500:
            try:
                sent = espnow_send(link, peer, "HALL|%d" % status)
                if sent:
                    last_sent = status
                    last_time = ticks_ms()
            except OSError:
                pass

    sleep_ms(20)
