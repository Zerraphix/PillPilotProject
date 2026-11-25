"""De fire statusser Main ESP32 maa sende. Ingen automatisk sensorlogik her."""
from pillpilot_api import _api_request

UDLEVERET = 2
IKKE_AFHENTET = 3
AFHENTET = 4
FEJL = 5

STATUS_CODES = {
    UDLEVERET: "udleveret",
    IKKE_AFHENTET: "ikke_afhentet",
    AFHENTET: "afhentet",
    FEJL: "fejl",
}


def set_udleveringsstatus(udlevering_id, status, fejlbeskrivelse=None):
    expected = STATUS_CODES[status]
    data = {"status_id": status}
    if status == FEJL:
        data["fejlbeskrivelse"] = fejlbeskrivelse or "Dispenser error"

    result = _api_request("PATCH", "/api/medicinudlevering/%s/status" % udlevering_id, data)
    if result["status_kode"] != expected:
        raise RuntimeError("API did not confirm the requested status")
    return result
