
import sys
import serial

from live_status import update_live_status, get_live_status
from uart_protocol import parse_uart_message


def read_uart(port):
    print(f"Forbinder til {port}...")

    with serial.Serial(port, 115200, timeout=2) as uart:
        print("UART klar. Venter på beskeder...")

        while True:
            raw = uart.readline(1025)

            if not raw:
                continue

            if not raw.endswith(b"\n"):
                print("Ufuldstændig eller for stor besked")
                continue

            try:
                message = parse_uart_message(raw)
                if update_live_status(message):
                    print(
                        "Live-status:",
                        get_live_status(message["enhed_id"])
                    )

                print("Besked modtaget!")
                print("Type:", message["type"])
                print("Enhed:", message["device"])
                print("Data:", message["data"])
                print()

            except ValueError as error:
                print("Ugyldig besked:", error)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Brug: python uart_reader.py <port>")
        sys.exit(1)

    try:
        read_uart(sys.argv[1])
    except serial.SerialException as error:
        print("UART-fejl:", error)
    except KeyboardInterrupt:
        print("\nUART-læser stoppet")
