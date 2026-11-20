
import json
import time

# Hoveddispenserens enhed_id
ENHED_ID = "PILL-001"

while True:
    message = {
        "type": "status",
        "enhed_id": ENHED_ID,
        "device": "armbaand",
        "data": {
            "battery_pct": 76
        }
    }

    print(json.dumps(message))
    time.sleep(2)

