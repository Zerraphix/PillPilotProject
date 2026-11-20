"""Gunicorn starter UART inde i samme worker som API'et.

RAM-delingen kræver præcis én worker, men må gerne have flere threads.
UART aktiveres først med UART_ENABLED=true i serverens .env.
"""

import os


def post_worker_init(worker):
    """Kaldes efter API'et er initialiseret i en Gunicorn-worker."""
    enabled = os.environ.get("UART_ENABLED", "false").strip().lower()
    if enabled not in {"1", "true", "yes"}:
        worker.log.info("UART-læseren er slået fra (UART_ENABLED=false)")
        return

    if worker.cfg.workers != 1:
        worker.log.error("UART-live-status kræver --workers 1; læseren blev ikke startet")
        return

    port = os.environ.get("UART_PORT", "/dev/ttyUSB0")
    try:
        baudrate = int(os.environ.get("UART_BAUD", "115200"))
        if baudrate <= 0:
            raise ValueError("baudrate skal være positiv")
    except ValueError:
        worker.log.error("Ugyldig UART_BAUD; læseren blev ikke startet")
        return

    from uart_reader import start_uart_reader
    start_uart_reader(port, baudrate)
    worker.log.info("UART-læser startet som baggrundstråd: %s (%s baud)", port, baudrate)
