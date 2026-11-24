"""De fire statusser Main ESP32 maa sende. Ingen automatisk sensorlogik her."""
from pillpilot_api import _api_request, get_udlevering, get_udleveringsstatusser

UDLEVERET = 2
IKKE_AFHENTET = 3
AFHENTET = 4
FEJL = 5
STATUS_KODER = {
    UDLEVERET: "udleveret",
    IKKE_AFHENTET: "ikke_afhentet",
    AFHENTET: "afhentet",
    FEJL: "fejl",
}


def set_udleveringsstatus(udlevering_id, status, forventet_tid=None):
    """Kun efter bekraeftet haendelse. Ved forpasset tid: angiv forventet_tid.

    GET-kontrol er ikke atomisk med PATCH; serveren skal ogsaa haandhaeve
    gyldige statusovergange. Returnerer den bekraeftede post eller None,
    hvis planen blev aendret inden PATCH.
    """
    if status not in STATUS_KODER:
        raise ValueError("ESP32 maa kun sende status 2, 3, 4 eller 5")
    kode = STATUS_KODER[status]
    statusser = get_udleveringsstatusser()
    if not any(row.get("kode") == kode and row.get("status_id") == status
               for row in statusser):
        raise ValueError("Status-ID/kode stemmer ikke med API: " + kode)

    current = get_udlevering(udlevering_id)
    if forventet_tid is not None:
        if status != FEJL:
            raise ValueError("forventet_tid bruges kun ved forpasset levering")
        if (current.get("status_kode") != "planlagt"
                or current.get("planlagt_tid") != forventet_tid):
            return None
    elif current.get("status_kode") == kode:
        return current  # Idempotent ved genforsoeg.
    else:
        allowed = {UDLEVERET: ("planlagt",), IKKE_AFHENTET: ("udleveret",),
                   AFHENTET: ("udleveret",), FEJL: ("planlagt", "udleveret")}
        if current.get("status_kode") not in allowed[status]:
            raise ValueError("Ugyldig statusovergang til " + kode)

    data = {"status_id": status}

    if status == FEJL:
        if forventet_tid is not None:
            data["fejlbeskrivelse"] = (
                "Planlagt udleveringsdato er overskredet."
            )
        else:
            data["fejlbeskrivelse"] = (
                "Dispenseren har registreret en fejl."
            )

    _api_request(
        "PATCH",
        "/api/medicinudlevering/%s/status" % int(udlevering_id),
        data
    )
    confirmed = get_udlevering(udlevering_id)
    if confirmed.get("status_kode") != kode:
        raise RuntimeError("PATCH-status kunne ikke bekraeftes: " + kode)
    return confirmed
