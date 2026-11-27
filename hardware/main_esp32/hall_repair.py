from pillpilot_api import connect_wifi
from espnow_link import espnow_init
from stepper_motor import stepper_init
from dispenser_controller import *

wifi = connect_wifi()
link, wifi = espnow_init(wifi)
motor = stepper_init()
state = controller_init()

controller_home(link, motor, state)