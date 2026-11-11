import sys
import select
from time import sleep_ms
from espnow_link import espnow_init
from stepper_motor import stepper_init, stepper_stop
from dispenser_controller import controller_init, controller_receive, controller_command

# Start ESP-NOW og motor
link, wifi = espnow_init(6)
motor = stepper_init()
state = controller_init()

# Lyt efter kommandoer via USB-seriel
poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

print("PillPilot motor klar")

try:
    while True:
        # Modtag Hall-sensorens status
        controller_receive(link, state, 20)

        # Linux sender HOME, NEXT|id eller STATUS
        if poll.poll(0):
            command = sys.stdin.readline().strip()
            if command:
                controller_command(command, link, motor, state)

        sleep_ms(10)
finally:
    stepper_stop(motor)
