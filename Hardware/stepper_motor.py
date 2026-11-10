
from machine import Pin
from time import sleep_ms

# Motorens halvtrin
SEQUENCE = [
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1)
]

# Motorindstillinger
MOTOR_SPEED = 10       # Millisekunder mellem trin
STEPS_PER_REV = 4096   # Trin pr. omgang


# Initialiser motoren
def stepper_init():
    return [
        Pin(16, Pin.OUT, value=0),
        Pin(17, Pin.OUT, value=0),
        Pin(18, Pin.OUT, value=0),
        Pin(19, Pin.OUT, value=0)
    ]

# Drej et antal trin
def stepper_move(motor, steps, delay_ms=MOTOR_SPEED):
    if delay_ms < 1:
        raise ValueError("Hastigheden skal være mindst 1 ms")
    direction = 1 if steps >= 0 else -1
    try:
        for i in range(abs(steps)):
            index = (i * direction) % 8

            for pin, value in zip(motor, SEQUENCE[index]):
                pin.value(value)
            sleep_ms(delay_ms)
    finally:
        stepper_stop(motor)

# Drej et antal grader
def stepper_rotate(motor, degrees, delay_ms=MOTOR_SPEED):
    steps = round(degrees * STEPS_PER_REV / 360)
    stepper_move(motor, steps, delay_ms)

# Drej til næste rum
def stepper_next(motor, delay_ms=MOTOR_SPEED):
    stepper_rotate(motor, 45, delay_ms)

# Drej til forrige rum
def stepper_previous(motor, delay_ms=MOTOR_SPEED):
    stepper_rotate(motor, -45, delay_ms)

# Sluk motoren
def stepper_stop(motor):
    for pin in motor:
        pin.value(0)

