"""JSON-lines til eksisterende UART-reader paa Raspberry Pi (USB/REPL)."""
import json
import sys
import select
import os
import config
from binascii import hexlify
from time import ticks_ms, ticks_diff

MAX_REPLY = 4096


def uart_request(operation, data=None):
    """One request at a time; ignore stale responses and bound the read time."""
    request_id = hexlify(os.urandom(8)).decode()
    enhed_id = config.ENHED_ID
    message = {"type": "request", "request_id": request_id,
               "enhed_id": enhed_id, "operation": operation,
               "data": data if data is not None else {}}
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)
    buf = bytearray()
    dropping = False
    print(json.dumps(message))
    start = ticks_ms()
    timeout_ms = getattr(config, "UART_TIMEOUT_MS", 12000)
    while ticks_diff(ticks_ms(), start) < timeout_ms:
        if not poller.poll(20):
            continue
        char = sys.stdin.read(1)
        if not char:
            continue
        if char == "\n":
            if dropping:
                dropping = False
                buf = bytearray()
                continue
            try:
                reply = json.loads(buf.decode())
            except (ValueError, UnicodeError):
                buf = bytearray()
                continue
            buf = bytearray()
            if (not isinstance(reply, dict)
                    or reply.get("type") != "response"
                    or reply.get("request_id") != request_id
                    or reply.get("enhed_id") != enhed_id):
                continue
            if reply.get("ok") is not True:
                error = reply.get("error", "UART request failed")
                if reply.get("retryable") is True:
                    raise OSError(error)
                raise RuntimeError(error)
            if "data" not in reply:
                raise RuntimeError("Invalid UART response")
            return reply
        if dropping or char == "\r":
            continue
        if len(buf) >= MAX_REPLY or ord(char) > 127:
            dropping = True
            buf = bytearray()
        else:
            buf.append(ord(char))
    raise OSError("UART response timeout")


def send_armband_status(battery_pct):
    if not getattr(config, "UART_LIVE_ENABLED", False):
        return False
    enhed_id = getattr(config, "ENHED_ID", "")
    if not enhed_id or type(battery_pct) is not int or not 0 <= battery_pct <= 100:
        return False
    print(json.dumps({"type": "status", "enhed_id": enhed_id,
                      "device": "armbaand", "data": {"battery_pct": battery_pct}}))
    return True
