import network
import espnow
from binascii import unhexlify


def espnow_init(channel=6):
    """Starter ESP-NOW paa den valgte Wi-Fi-kanal."""
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.disconnect()
    wifi.config(channel=channel)

    link = espnow.ESPNow()
    link.active(True)
    return link, wifi


def espnow_mac(wifi):
    """Returnerer ESP32-enhedens MAC-adresse som tekst."""
    return ":".join("%02X" % number for number in wifi.config("mac"))


def espnow_add_peer(link, address):
    """Tilfoejer en ESP32-enhed, som vi maa sende beskeder til."""
    address_bytes = unhexlify(address.replace(":", ""))
    if len(address_bytes) != 6:
        raise ValueError("Ugyldig MAC-adresse")

    link.add_peer(address_bytes)
    return address_bytes


def espnow_send(link, peer, message):
    """Sender en tekstbesked til den valgte ESP32."""
    return link.send(peer, message.encode())


def espnow_receive(link, timeout_ms=1000):
    """Modtager en tekstbesked og afsenderens MAC-adresse."""
    mac, message = link.recv(timeout_ms)
    if message is None:
        return None

    sender = ":".join("%02X" % number for number in mac)
    return sender, message.decode()
