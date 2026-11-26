"""Læs UART-beskeder fra ESP32, og opdater live_status i samme proces.

Manuel test: uv run python uart_reader.py /dev/ttyUSB0
Produktion: starter i Gunicorn-worker via gunicorn.conf.py.
"""

import logging
import sys
import time
from threading import Thread

import serial

from live_status import update_live_status
from uart_protocol import MAX_MESSAGE_SIZE, parse_uart_message

logger = logging.getLogger("gunicorn.error")
_uart_thread = None


def read_uart(port: str, baudrate: int = 115200) -> None:
    """Læser én seriel forbindelse, indtil den afbrydes eller stoppes."""
    with serial.Serial(port, baudrate, timeout=2) as uart:
        logger.info("UART forbundet til %s", port)
        while True:
            raw = uart.readline(MAX_MESSAGE_SIZE + 2)
            if not raw:
                continue
            
            if not raw.strip().startswith(b"{"):
                logger.info(
                    "ESP32: %s",
                    raw.decode("utf-8", errors="replace").strip()
                )
                continue

            if not raw.endswith(b"\n"):
                logger.warning("UART: ufuldstændig eller for lang besked")
                if len(raw) >= MAX_MESSAGE_SIZE + 2:
                    while raw and not raw.endswith(b"\n"):
                        raw = uart.readline(MAX_MESSAGE_SIZE + 2)
                continue

            try:
                message = parse_uart_message(raw)
                if update_live_status(message):
                    logger.info(
                        "UART status: enhed_id=%s, device=%s",
                        message["enhed_id"], message["device"],
                    )
            except ValueError as error:
                logger.warning("UART: ugyldig besked: %s", error)


def read_uart_forever(port: str, baudrate: int = 115200) -> None:
    """Genopretter forbindelsen, hvis ESP32 eller USB-kablet afbrydes."""
    while True:
        try:
            read_uart(port, baudrate)
        except (serial.SerialException, OSError) as error:
            logger.warning("UART: kan ikke læse %s: %s", port, error)
        time.sleep(3)


def start_uart_reader(port: str, baudrate: int = 115200) -> None:
    """Starter højst én UART-tråd i denne Python-proces."""
    global _uart_thread
    if _uart_thread is not None and _uart_thread.is_alive():
        return

    _uart_thread = Thread(
        target=read_uart_forever,
        args=(port, baudrate),
        daemon=True,
        name="pillpilot-uart",
    )
    _uart_thread.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(sys.argv) != 2:
        print("Brug: uv run python uart_reader.py /dev/ttyUSB0")
        sys.exit(1)
    try:
        read_uart(sys.argv[1])
    except (serial.SerialException, OSError) as error:
        print("UART-fejl:", error)
    except KeyboardInterrupt:
        print("\nUART-læser stoppet")
