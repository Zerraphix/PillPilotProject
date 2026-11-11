from machine import Pin
from time import sleep_ms

# Motorindstillinger
MOTOR_SPEED = 10
STEPS_PER_REV = 4096
COMPARTMENTS = 8

# Halvtrin for 28BYJ-48
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


# Start motoren

def stepper_init():
    pins = [Pin(n, Pin.OUT, value=0) for n in (16, 17, 18, 19)]
    return {"pins": pins, "phase": 0}


# Drej et halvtrin

def stepper_step(motor, direction=1, delay_ms=MOTOR_SPEED):
    motor["phase"] = (motor["phase"] + direction) % 8
    values = SEQUENCE[motor["phase"]]
    for pin, value in zip(motor["pins"], values):
        pin.value(value)
    sleep_ms(delay_ms)


# Drej flere halvtrin

def stepper_move(motor, steps, delay_ms=MOTOR_SPEED):
    direction = 1 if steps >= 0 else -1
    try:
        for _ in range(abs(steps)):
            stepper_step(motor, direction, delay_ms)
    finally:
        stepper_stop(motor)


# Drej et antal grader

def stepper_rotate(motor, degrees, delay_ms=MOTOR_SPEED):
    steps = round(degrees * STEPS_PER_REV / 360)
    stepper_move(motor, steps, delay_ms)


# Drej til naeste rum

def stepper_next(motor, delay_ms=MOTOR_SPEED):
    stepper_rotate(motor, 360 / COMPARTMENTS, delay_ms)


# Sluk motoren

def stepper_stop(motor):
    for pin in motor["pins"]:
        pin.value(0)
