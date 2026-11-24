import json
import time

while True:
    message = {
        "type": "status",
        "device": "armbaand",
        "data": {
            "battery_pct": 76
        }
    }

    print(json.dumps(message))
    time.sleep(2)