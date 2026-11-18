
from machine import ADC, Pin
from time import sleep

usb = ADC(Pin(1))
usb.atten(ADC.ATTN_11DB)

while True:
    raw = usb.read()
    voltage = usb.read_uv() / 1000000

    print("ADC raavaerdi:", raw)
    print("D1 spaending: {:.3f} V".format(voltage))
    print("Beregnet USB: {:.3f} V".format(voltage * 2))
    print("---------------------")

    sleep(2)
