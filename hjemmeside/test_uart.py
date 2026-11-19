
from uart_protocol import parse_uart_message

# Simulerer en besked modtaget over UART
raw_message = b'{"type":"status","device":"armbaand","data":{"battery_pct":76}}\n'

try:
    message = parse_uart_message(raw_message)

    print("Besked modtaget!")
    print("Type:", message["type"])
    print("Enhed:", message["device"])
    print("Data:", message["data"])

except ValueError as error:
    print("Fejl:", error)
