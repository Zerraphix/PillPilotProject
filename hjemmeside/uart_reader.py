"""Læs UART-beskeder fra ESP32, og opdater live_status i samme proces.

Manuel test: uv run python uart_reader.py /dev/ttyUSB0
Produktion: starter i Gunicorn-worker via gunicorn.conf.py.
"""
import http.client
import json
import logging
import os
import sys
import time
from threading import Thread

import serial

from live_status import update_live_status
from uart_protocol import MAX_MESSAGE_SIZE, parse_uart_message

logger = logging.getLogger("gunicorn.error")
_uart_thread = None
MAX_REPLY = 4096
MAX_REQUEST = max(MAX_MESSAGE_SIZE, 1024)
MAX_API_BODY = 256 * 1024
STATUS_CODES = {2: "udleveret", 3: "ikke_afhentet", 4: "afhentet", 5: "fejl"}
ACTIVE_STATUSES = {"planlagt", "udleveret", "ikke_afhentet"}


class ApiError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Local API HTTP {status}")


def api_request(method, path, key, data=None):
    # Never accept a URL or arbitrary path from the ESP32.
    conn = http.client.HTTPConnection("127.0.0.1", 5000, timeout=4)
    headers = {"X-Device-Key": key, "Accept": "application/json",
               "Cache-Control": "no-cache", "Connection": "close"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        if not 200 <= response.status < 300:
            raise ApiError(response.status)
        raw = response.read(MAX_API_BODY + 1)
        if len(raw) > MAX_API_BODY:
            raise ValueError("Local API response too large")
        return json.loads(raw), response.getheader("Date")
    finally:
        conn.close()


def compact_delivery(row):
    return {name: row[name] for name in (
        "udlevering_id", "status_kode", "planlagt_tid", "afhentningsfrist")}


def handle_request(message, enhed_id, key):
    if message.get("enhed_id") != enhed_id or not key or not enhed_id:
        raise ValueError("UART dispenser not configured or not authorized")
    operation = message.get("operation")
    data = message.get("data")
    if not isinstance(data, dict):
        raise ValueError("Invalid UART data")
    if operation == "get_deliveries":
        rows, date = api_request("GET", "/api/medicinudlevering", key)
        if not isinstance(rows, list) or not date:
            raise ValueError("Invalid delivery list or server time")
        rows = [compact_delivery(row) for row in rows if row["status_kode"] in ACTIVE_STATUSES]
        if len(rows) > 16:
            raise ValueError("Too many active deliveries; inspect plan")
        return rows, date
    if operation == "get_statuses":
        return api_request("GET", "/api/udleveringsstatus", key)
    if operation not in ("get_delivery", "set_delivery_status"):
        raise ValueError("Unknown UART operation")
    ident = data.get("udlevering_id")
    if type(ident) is not int or ident <= 0:
        raise ValueError("Invalid delivery ID")
    path = f"/api/medicinudlevering/{ident}"
    if operation == "get_delivery":
        return api_request("GET", path, key)
    status = data.get("status_id")
    if type(status) is not int or status not in STATUS_CODES:
        raise ValueError("Invalid device status")
    payload = {"status_id": status}
    if status == 5:
        reason = data.get("fejlbeskrivelse")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 240:
            raise ValueError("Invalid failure description")
        payload["fejlbeskrivelse"] = reason
    # A lost UART acknowledgement must not cause another status transition.
    current, date = api_request("GET", path, key)
    if current["status_kode"] == STATUS_CODES[status]:
        if status == 5 and current.get("fejlbeskrivelse") != payload["fejlbeskrivelse"]:
            raise ValueError("Existing failure description differs; inspect delivery")
        return {"status_kode": current["status_kode"]}, date
    result, date = api_request("PATCH", path + "/status", key, payload)
    if result["status_kode"] != STATUS_CODES[status]:
        raise ValueError("API did not confirm status")
    return {"status_kode": result["status_kode"]}, date


def send_response(uart, message, enhed_id, key):
    request_id = message.get("request_id")
    if (not isinstance(request_id, str) or len(request_id) != 16
            or any(c not in "0123456789abcdef" for c in request_id)):
        logger.warning("UART: invalid request ID")
        return
    reply = {"type": "response", "request_id": request_id,
             "enhed_id": message.get("enhed_id"), "ok": False}
    try:
        data, date = handle_request(message, enhed_id, key)
        reply.update(ok=True, data=data, date=date)
    except ApiError as error:
        reply.update(error=str(error), retryable=error.status >= 500 or error.status == 429)
    except (OSError, http.client.HTTPException) as error:
        logger.warning("UART local API connection failed: %s", type(error).__name__)
        reply.update(error="Local API unavailable", retryable=True)
    except (ValueError, TypeError, KeyError) as error:
        logger.warning("UART request rejected: %s", error)
        reply.update(error="Invalid UART request or API data", retryable=False)
    raw = json.dumps(reply, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(raw) > MAX_REPLY:
        reply = {"type": "response", "request_id": request_id,
                 "enhed_id": message.get("enhed_id"), "ok": False,
                 "error": "UART response too large", "retryable": False}
        raw = json.dumps(reply, ensure_ascii=True).encode("ascii")
    logger.info("UART response size: %s bytes", len(raw))

    payload = raw + b"\n"

    for i in range(0, len(payload), 64):
        uart.write(payload[i:i + 64])
        uart.flush()
        time.sleep(0.02)
    logger.info("UART RPC: operation=%s ok=%s", message.get("operation"), reply["ok"])


def read_uart(port: str, baudrate: int = 115200) -> None:
    enhed_id = os.environ.get("UART_DEVICE_ID", "")
    key = os.environ.get("UART_DEVICE_KEY", "")
    if not enhed_id or not key:
        logger.warning("UART: set UART_DEVICE_ID and UART_DEVICE_KEY in service environment")
    with serial.Serial(port, baudrate, timeout=2, write_timeout=3) as uart:
        logger.info("UART forbundet til %s", port)
        dropping = False
        while True:
            raw = uart.readline(MAX_REQUEST + 2)
            if not raw:
                continue
            if dropping or len(raw) > MAX_REQUEST + 1 or not raw.endswith(b"\n"):
                dropping = not raw.endswith(b"\n")
                logger.warning("UART: ufuldstændig eller for lang besked")
                continue
            if not raw.lstrip().startswith(b"{"):
                logger.info("ESP32: %s", raw.decode("utf-8", errors="replace").strip())
                continue
            try:
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    raise ValueError("JSON object required")
                if obj.get("type") == "request":
                    send_response(uart, obj, enhed_id, key)
                else:
                    message = parse_uart_message(raw)
                    if not enhed_id or message["enhed_id"] != enhed_id:
                        raise ValueError("Unexpected device ID")
                    if update_live_status(message):
                        logger.info("UART status: enhed_id=%s, device=%s",
                                    message["enhed_id"], message["device"])
            except (ValueError, TypeError, KeyError) as error:
                logger.warning("UART: ugyldig besked: %s", error)


def read_uart_forever(port: str, baudrate: int = 115200) -> None:
    while True:
        try:
            read_uart(port, baudrate)
        except (serial.SerialException, OSError) as error:
            logger.warning("UART: kan ikke læse %s: %s", port, error)
        time.sleep(3)


def start_uart_reader(port: str, baudrate: int = 115200) -> None:
    global _uart_thread
    if _uart_thread is not None and _uart_thread.is_alive():
        return
    _uart_thread = Thread(target=read_uart_forever, args=(port, baudrate),
                          daemon=True, name="pillpilot-uart")
    _uart_thread.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(sys.argv) != 2:
        print("Brug: uv run python uart_reader.py /dev/ttyUSB0")
        sys.exit(1)
    try:
        read_uart(sys.argv[1])
    except KeyboardInterrupt:
        print("\nUART-læser stoppet")
