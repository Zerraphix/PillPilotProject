import sys
import select
import asyncio
from espnow_link import espnow_init
from stepper_motor import stepper_init, stepper_stop
from dispenser_controller import controller_init, controller_receive, controller_command
from ble_armband import armband_command


link, wifi = espnow_init(6)
motor = stepper_init()
state = controller_init()

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)


async def main():
    """Modtager status fra Hall-sensoren og kommandoer fra USB."""
    print("PillPilot controller klar")

    while True:
        controller_receive(link, state, 20)

        if poll.poll(0):
            command = sys.stdin.readline().strip()

            if command == "REMIND" or command == "BATTERY":
                await armband_command(command)
            elif command:
                controller_command(command, link, motor, state)

        await asyncio.sleep_ms(10)


try:
    asyncio.run(main())
finally:
    stepper_stop(motor)
