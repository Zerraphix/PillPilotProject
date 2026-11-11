import network
import espnow
from binascii import unhexlify


# Start ESP-NOW

def espnow_init(channel=6):
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.disconnect()
    wifi.config(channel=channel)

    link = espnow.ESPNow()
    link.active(True)
    return link, wifi


# Hent MAC-adressen

def espnow_mac(wifi):
    return ":".join("%02X" % b for b in wifi.config("mac"))


# Tilfoej en ESP32

def espnow_add_peer(link, address):
    mac = unhexlify(address.replace(":", ""))
    if len(mac) != 6:
        raise ValueError("Ugyldig MAC-adresse")
    link.add_peer(mac)
    return mac


# Send en besked

def espnow_send(link, peer, message):
    return link.send(peer, message.encode())


# Modtag en besked

def espnow_receive(link, timeout_ms=1000):
    mac, message = link.recv(timeout_ms)
    if message is None:
        return None
    sender = ":".join("%02X" % b for b in mac)
    return sender, message.decode()
