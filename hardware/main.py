"""Manuel gennemgang af eksisterende PillPilot-API fra ESP32.

Henter planlagte udleveringer. Opdaterer KUN ved bevidst bekræftelse
fra Thonny. Senere kaldes registrer_udleveret() af motor/sensor-logik.
"""

from pillpilot_api import (
    connect_wifi,
    get_udleveringer,
    get_udlevering,
    registrer_udleveret,
)


def main():
    connect_wifi()
    print("\nHenter udleveringer fra PillPilot...")
    alle = get_udleveringer()
    planlagte = [u for u in alle if u.get("status_kode") == "planlagt"]
    planlagte.sort(key=lambda u: u["planlagt_tid"])

    print("Planlagte udleveringer:", len(planlagte))
    for u in planlagte[:10]:
        print("  ID: %s | %s | %s" % (
            u["udlevering_id"], u["planlagt_tid"], u["medicinplan_navn"]))

    if not planlagte:
        print("Ingen planlagte udleveringer.")
        return

    # Ingen automatisk ændring af udleveringer.
    udvalgt = planlagte[0]
    ident = udvalgt["udlevering_id"]
    print("\nNæste planlagte udlevering: %s" % ident)
    print("Status før:", get_udlevering(ident)["status_kode"])

    svar = input("Skriv LEVERET for at ændre denne post (ellers Enter): ")
    if svar != "LEVERET":
        print("Ingen ændringer skrevet til databasen.")
        return

    resultat = registrer_udleveret(ident)
    print("PATCH status:", resultat["status_kode"])
    print("GET status efter:", get_udlevering(ident)["status_kode"])


main()
