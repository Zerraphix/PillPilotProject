"""Koeres paa PC/Linux, ikke paa ESP32. Kraever: pip install pyserial"""
import sys
import time
import serial


def send_command(port, command):
    with serial.Serial(port, baudrate=115200, timeout=1) as device:
        # Giv ESP32 tid til at starte, hvis USB-aabning giver reset
        time.sleep(2)
        device.reset_input_buffer()
        device.write((command + "\n").encode("ascii"))
        deadline = time.time() + (55 if command == "HOME" else 12)
        while time.time() < deadline:
            line = device.readline()
            if line:
                print(line.decode("utf-8", errors="replace").strip())
                if line.startswith((b"HOME|", b"NEXT|", b"STATUS|", b"FEJL|", b"IGNORERET|")):
                    break


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Brug: python send_command.py COM4 HOME")
        print("Brug: python send_command.py COM4 NEXT|test001")
    else:
        send_command(sys.argv[1], sys.argv[2])
