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
        raise OSError("WiFi kunne ikke forbinde, status: %s" % wlan.status())

    print("WiFi forbundet:", wlan.ifconfig()[0])
    return wlan


def _api_request(method, path, data=None):
    url = API_URL.rstrip("/") + path
    headers = {"X-Device-Key": DEVICE_API_KEY, "Accept": "application/json"}
    kwargs = {"headers": headers}

    if data is not None:
        headers["Content-Type"] = "application/json"
        kwargs["data"] = json.dumps(data)

    response = None
    try:
        response = requests.request(method, url, **kwargs)
        status = response.status_code
        body = response.text
    finally:
        if response is not None:
            response.close()

    if status < 200 or status >= 300:
        raise RuntimeError("API %s %s gav HTTP %s: %s" % (
            method, path, status, body[:240]))
    return json.loads(body) if body else None


def get_udleveringer():
    """API'en skal begrænse resultatet til denne godkendte dispenser."""
    return _api_request("GET", "/api/medicinudlevering")


def get_udlevering(udlevering_id):
    return _api_request("GET", "/api/medicinudlevering/%s" % int(udlevering_id))


def get_udleveringsstatusser():
    return _api_request("GET", "/api/udleveringsstatus")


def get_naeste_planlagte_udlevering():
    planlagte = [u for u in get_udleveringer()
                 if u.get("status_kode") == "planlagt"]
    planlagte.sort(key=lambda u: u["planlagt_tid"])
    return planlagte[0] if planlagte else None


def registrer_udleveret(udlevering_id):
    """Kald kun, NÅR den fysiske dispenser faktisk har udleveret.

    Til udvikling kan den kaldes manuelt på syntetiske databaseposter.
    """
    statusser = get_udleveringsstatusser()
    status_id = None
    for row in statusser:
        if row.get("kode") == "udleveret":
            status_id = row["status_id"]
            break
    if status_id is None:
        raise ValueError("Statuskoden 'udleveret' findes ikke")

    return _api_request(
        "PATCH",
        "/api/medicinudlevering/%s/status" % int(udlevering_id),
        {"status_id": status_id},
    )
