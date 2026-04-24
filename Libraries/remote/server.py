"""Servidor TCP que expone los instrumentos USB conectados a la Raspberry Pi.

Corre en la Pi (clonar este repo, PYTHONPATH=Libraries, ejecutar este archivo).
Escucha en 0.0.0.0:5555 por default. Maneja múltiples conexiones con un lock
global (los instrumentos no son thread-safe).

Uso:
    PYTHONPATH=Libraries venv/bin/python Libraries/remote/server.py

Con flags:
    --host 0.0.0.0 --port 5555 --no-utg --no-dmm
"""

import argparse
import logging
import socket
import sys
import threading

from remote.protocol import (
    DEFAULT_PORT,
    DEVICE_UT61EPLUS,
    DEVICE_UTG932E,
    LineSocket,
    decode_request,
    encode_error,
    encode_ok,
)

log = logging.getLogger("remote.server")


class InstrumentRegistry:
    """Mantiene las instancias de instrumentos y un lock global para serializarlas."""

    def __init__(self):
        self._devices = {}
        self._lock = threading.Lock()

    def register(self, name, instance):
        self._devices[name] = instance

    def call(self, device, method, args, kwargs):
        if device not in self._devices:
            raise ValueError(f"Unknown or disabled device: {device}")
        inst = self._devices[device]
        if method.startswith("_"):
            raise ValueError(f"Private method not callable: {method}")
        fn = getattr(inst, method, None)
        if fn is None or not callable(fn):
            raise AttributeError(f"{device} has no method {method!r}")
        with self._lock:
            return fn(*args, **kwargs)


def handle_client(conn, addr, registry):
    log.info("Client connected: %s", addr)
    line_sock = LineSocket(conn)
    try:
        while True:
            line = line_sock.recv_line()
            if not line:
                break
            try:
                device, method, args, kwargs = decode_request(line)
                result = registry.call(device, method, args, kwargs)
                line_sock.send_line(encode_ok(result))
            except Exception as e:
                log.warning("Request error from %s: %s: %s", addr, type(e).__name__, e)
                line_sock.send_line(encode_error(e))
    except ConnectionError as e:
        log.info("Client %s disconnected: %s", addr, e)
    except Exception:
        log.exception("Unexpected error handling %s", addr)
    finally:
        line_sock.close()
        log.info("Client disconnected: %s", addr)


def init_utg932e(registry):
    from unit_utg932e.utg962_local import Utg962Local
    try:
        registry.register(DEVICE_UTG932E, Utg962Local())
        log.info("UTG932E initialized")
    except Exception as e:
        log.error("Failed to init UTG932E: %s", e)


def init_ut61eplus(registry):
    from unit_ut61eplus.ut61eplus.ut61eplus_local import UT61EPLUSLocal
    try:
        registry.register(DEVICE_UT61EPLUS, UT61EPLUSLocal())
        log.info("UT61E+ initialized")
    except Exception as e:
        log.error("Failed to init UT61E+: %s", e)


def serve(host, port, registry):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(4)
        log.info("Listening on %s:%d", host, port)
        while True:
            conn, addr = srv.accept()
            t = threading.Thread(
                target=handle_client, args=(conn, addr, registry), daemon=True
            )
            t.start()


def main():
    parser = argparse.ArgumentParser(description="Lab instrument TCP bridge")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-utg", action="store_true", help="No inicializar UTG932E")
    parser.add_argument("--no-dmm", action="store_true", help="No inicializar UT61E+")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    registry = InstrumentRegistry()
    if not args.no_utg:
        init_utg932e(registry)
    if not args.no_dmm:
        init_ut61eplus(registry)

    if not registry._devices:
        log.error("No devices initialized, exiting")
        sys.exit(1)

    try:
        serve(args.host, args.port, registry)
    except KeyboardInterrupt:
        log.info("Shutting down")


if __name__ == "__main__":
    main()
