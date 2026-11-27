"""Faelles ESP-NOW-forbindelse. Bevarer Wi-Fi forbindelsen til API'et."""
import network
import espnow
import config
from binascii import unhexlify


def espnow_init(wifi=None):
    if wifi is None:
        link = espnow.ESPNow()
        link.active(False)
        wifi = network.WLAN(network.STA_IF)
        wifi.active(False)
        network.WLAN(network.AP_IF).active(False)
        wifi.active(True)
        wifi.config(reconnects=0)
        if wifi.isconnected():
            wifi.disconnect()
        wifi.config(channel=getattr(config, "ESPNOW_CHANNEL", 10))
        wifi.config(pm=network.WLAN.PM_NONE)
    else:
        link = espnow.ESPNow()
    link.active(True)
    return link, wifi


def espnow_mac(wifi):
    return ":".join("%02X" % number for number in wifi.config("mac"))


def espnow_add_peer(link, address):
    address_bytes = unhexlify(address.replace(":", ""))
    if len(address_bytes) != 6:
        raise ValueError("Invalid MAC address")
    link.add_peer(address_bytes)
    return address_bytes


def espnow_send(link, peer, message):
    return link.send(peer, message.encode())


def espnow_receive(link, timeout_ms=0):
    mac, message = link.recv(timeout_ms)
    if message is None:
        return None
    return ":".join("%02X" % number for number in mac), message.decode()
