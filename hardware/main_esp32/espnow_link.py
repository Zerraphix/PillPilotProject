"""Faelles ESP-NOW-forbindelse. Bevarer Wi-Fi forbindelsen til API'et."""
import network
import espnow
from binascii import unhexlify


def espnow_init(wifi=None):
    """Aktiverer ESP-NOW paa den allerede aktive Wi-Fi kanal.

    Hvis STA er forbundet til en router, bestemmer routeren kanalen.
    Kald derfor connect_wifi() foerst paa hoved-ESP32'en.
    """
    if wifi is None:
        wifi = network.WLAN(network.STA_IF)
        wifi.active(True)

    link = espnow.ESPNow()
    link.active(True)
    return link, wifi


def espnow_mac(wifi):
    return ":".join("%02X" % number for number in wifi.config("mac"))


def espnow_add_peer(link, address):
    address_bytes = unhexlify(address.replace(":", ""))
    if len(address_bytes) != 6:
        raise ValueError("Ugyldig MAC-adresse")
    link.add_peer(address_bytes)
    return address_bytes


def espnow_send(link, peer, message):
    return link.send(peer, message.encode())


def espnow_receive(link, timeout_ms=0):
    """Returnerer (afsender_MAC, tekst) eller None uden at blokere."""
    mac, message = link.recv(timeout_ms)
    if message is None:
        return None
    return ":".join("%02X" % number for number in mac), message.decode()
