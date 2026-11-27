from machine import Pin
from time import sleep_ms


MOTOR_SPEED = 3
STEPS_PER_REV = 4096
COMPARTMENTS = 8

SEQUENCE = (
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
)


def stepper_init():
    """Starter motorens fire styreben paa controlleren."""
    pins = [Pin(number, Pin.OUT, value=0) for number in (32, 33, 25, 26)]
    return {"pins": pins, "phase": 0}


def stepper_step(motor, direction=1, delay_ms=MOTOR_SPEED):
    """Flytter motoren et halvtrin i den valgte retning."""
    motor["phase"] = (motor["phase"] + direction) % 8
    values = SEQUENCE[motor["phase"]]

    for pin, value in zip(motor["pins"], values):
        pin.value(value)

    sleep_ms(delay_ms)


def stepper_move(motor, steps, delay_ms=MOTOR_SPEED):
    """Flytter motoren det oenskede antal halvtrin."""
    direction = 1 if steps >= 0 else -1

    try:
        for i in range(abs(steps)):
            stepper_step(motor, direction, delay_ms)
    finally:
        stepper_stop(motor)


def stepper_rotate(motor, degrees, delay_ms=MOTOR_SPEED):
    """Drejer motoren et bestemt antal grader."""
    steps = round(degrees * STEPS_PER_REV / 360)
    stepper_move(motor, steps, delay_ms)


def stepper_next(motor, delay_ms=MOTOR_SPEED):
    """Drejer dispenseren til naeste af de otte medicinrum."""
    stepper_rotate(motor, 360 / COMPARTMENTS, delay_ms)


def stepper_stop(motor):
    """Slukker signalerne til stepmotoren."""
    for pin in motor["pins"]:
        pin.value(0)
        
    