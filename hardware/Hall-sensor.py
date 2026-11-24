
from stepper_motor import (
    stepper_init,
    stepper_rotate,
    stepper_next,
    stepper_previous,
    stepper_stop
)

from time import sleep


# Initialiser motor
motor = stepper_init(16, 17, 18, 19)

try:
    # Drej 45 grader frem
    print("Drejer 45 grader frem")
    stepper_next(motor)
    sleep(2)

    # Drej 45 grader tilbage
    print("Drejer 45 grader tilbage")
    stepper_previous(motor)
    sleep(2)

    # Drej en hel omgang
    print("Drejer 360 grader")
    stepper_rotate(motor, 360)

    print("Test gennemført")

finally:
    # Sluk motoren
    stepper_stop(motor)
