
from uart_protocol import parse_uart_message
from live_status import update_live_status, get_live_status

# To forskellige hoveddispensere
test_messages = [
    b'{"type":"status","enhed_id":"PILL-001","device":"armbaand","data":{"battery_pct":76}}\n',
    b'{"type":"status","enhed_id":"PILL-002","device":"armbaand","data":{"battery_pct":43}}\n'
]

for raw in test_messages:
    try:
        message = parse_uart_message(raw)
        update_live_status(message)

        print("Modtaget fra:", message["enhed_id"])
        print("Data:", message["data"])
        print()

    except ValueError as error:
        print("Fejl:", error)

print("Status for PILL-001:")
print(get_live_status("PILL-001"))

print("\nStatus for PILL-002:")
print(get_live_status("PILL-002"))
