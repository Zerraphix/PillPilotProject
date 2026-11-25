"""PillPilot MicroPython-klient til EKSISTERENDE API-endpoints.

Der oprettes ikke nye endpoints, ingen medicin udleveres af denne fil.
Brug kun en midlertidig enhedsnøgle over HTTP i et isoleret demomiljø.
"""

import json
import time
import network

try:
    import requests
except ImportError:
    import urequests as requests

import config
from config import WIFI_SSID, WIFI_PASSWORD, API_URL, DEVICE_API_KEY


def connect_wifi(timeout_seconds=20):
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        wlan.active(False)
        time.sleep(1)
        wlan.active(True)
        time.sleep(1)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        for _ in range(timeout_seconds):
            if wlan.isconnected():
                break
            time.sleep(1)

    if not wlan.isconnected():
        raise OSError("WiFi connection failed, status: %s" % wlan.status())

    wlan.config(pm=network.WLAN.PM_NONE)
    print("WiFi connected:", wlan.ifconfig()[0])
    return wlan


def _api_request(method, path, data=None, with_date=False):
    url = API_URL.rstrip("/") + path
    headers = {"X-Device-Key": DEVICE_API_KEY, "Accept": "application/json"}
    kwargs = {"headers": headers, "timeout": getattr(config, "API_TIMEOUT_SECONDS", 5)}
    if with_date:
        headers["Cache-Control"] = "no-cache"
    server_date = None

    if data is not None:
        headers["Content-Type"] = "application/json"
        kwargs["data"] = json.dumps(data)

    response = None
    try:
        response = requests.request(method, url, **kwargs)
        status = response.status_code
        if with_date:
            response_headers = getattr(response, "headers", None) or {}
            if hasattr(response_headers, "items"):
                pairs = response_headers.items()
            else:
                pairs = []
                for line in response_headers:
                    if isinstance(line, bytes):
                        line = line.decode()
                    if ":" in line:
                        pairs.append(line.split(":", 1))
            for key, value in pairs:
                if isinstance(key, bytes):
                    key = key.decode()
                if key.lower() == "date":
                    server_date = (value.decode() if isinstance(value, bytes) else value).strip()
                    break
        body = response.text
    finally:
        if response is not None:
            response.close()

    if status < 200 or status >= 300:
        raise RuntimeError("API %s %s returned HTTP %s: %s" % (
            method, path, status, body[:240]))
    result = json.loads(body) if body else None
    return (result, server_date) if with_date else result


def get_udleveringer(with_date=False):
    """API'en skal begrænse resultatet til denne godkendte dispenser."""
    return _api_request("GET", "/api/medicinudlevering", with_date=with_date)


def get_udlevering(udlevering_id):
    return _api_request("GET", "/api/medicinudlevering/%s" % int(udlevering_id))


def get_udleveringsstatusser():
    return _api_request("GET", "/api/udleveringsstatus")
