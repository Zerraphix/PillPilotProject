"""PillPilot MicroPython-klient til EKSISTERENDE API-endpoints.

Der oprettes ikke nye endpoints, ingen medicin udleveres af denne fil.
"""
from uart_link import uart_request


def _api_request(method, path, data=None, with_date=False):
    # Preserve the interface used by delivery_schedule and delivery_status.
    if method == "GET" and path == "/api/medicinudlevering":
        reply = uart_request("get_deliveries")
    elif method == "GET" and path == "/api/udleveringsstatus":
        reply = uart_request("get_statuses")
    elif path.startswith("/api/medicinudlevering/"):
        tail = path[len("/api/medicinudlevering/"):].split("/")
        ident = int(tail[0])
        if method == "GET" and len(tail) == 1:
            reply = uart_request("get_delivery", {"udlevering_id": ident})
        elif method == "PATCH" and len(tail) == 2 and tail[1] == "status":
            payload = {"udlevering_id": ident, "status_id": data["status_id"]}
            if "fejlbeskrivelse" in data:
                payload["fejlbeskrivelse"] = data["fejlbeskrivelse"]
            reply = uart_request("set_delivery_status", payload)
        else:
            raise ValueError("Unsupported UART operation")
    else:
        raise ValueError("Unsupported UART operation")
    result = reply["data"]
    return (result, reply.get("date")) if with_date else result


def get_udleveringer(with_date=False):
    """API'en skal begrænse resultatet til denne godkendte dispenser."""
    return _api_request("GET", "/api/medicinudlevering", with_date=with_date)


def get_udlevering(udlevering_id):
    return _api_request("GET", "/api/medicinudlevering/%s" % int(udlevering_id))


def get_udleveringsstatusser():
    return _api_request("GET", "/api/udleveringsstatus")
