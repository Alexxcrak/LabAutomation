"""Cliente TCP del generador UTG932E/UTG962E.

La API replica a `Utg962Local` (ver utg962_local.py). Cualquier método que
no requiera lógica del lado cliente se delega al servidor via __getattr__.

Métodos soportados (ejecutados remotamente):
    get_idn, reset,
    set_system_lock, get_system_lock,
    set_system_language, get_system_language,
    set_system_beep, get_system_beep,
    set_system_brightness, get_system_brightness,
    set_system_sleep, get_system_sleep,
    set_channel_output, get_channel_output,
    set_channel_inversion, get_channel_inversion,
    load_arb_from_list,
    set_arb, set_ramp, set_sine, set_square, set_dc, set_output
"""

import os
import socket
import time

from remote.protocol import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEVICE_UTG932E,
    LineSocket,
    RemoteError,
    encode_request,
    decode_response,
)


class UtgError(Exception):
    pass


class Utg962:
    def __init__(self, host=None, port=None, timeout=20.0):
        self._host = host or os.environ.get("LAB_HOST", DEFAULT_HOST)
        self._port = int(port or os.environ.get("LAB_PORT", DEFAULT_PORT))
        self._timeout = timeout
        self._line = None
        self._connect()

    def _connect(self):
        """(Re)abre el socket al server de la Pi con keepalive, reintentando con backoff.

        El power-save del WiFi de la Pi corta conexiones TCP ociosas y mientras la
        radio despierta puede rechazar o timeoutear la conexión. Reintentar cubre
        tanto la conexión inicial (`__init__`) como las reconexiones de `_call`. El
        keepalive mantiene vivo el flujo durante los segundos ociosos de baja frec.
        """
        last = None
        for attempt in range(6):
            if attempt:
                time.sleep(min(attempt, 4))
            try:
                sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
                sock.settimeout(self._timeout)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if hasattr(socket, "TCP_KEEPIDLE"):
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 2)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 2)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                self._line = LineSocket(sock)
                return
            except (ConnectionError, TimeoutError, OSError) as e:
                last = e
        raise last

    def close(self) -> None:
        """Cierra solo la conexión TCP; el instrumento en la Pi queda disponible."""
        self._line.close()

    def load_arb_from_file(self, arb_index: int, arb_name: str, filename: str) -> None:
        """Lee el archivo local y envía los puntos al servidor via load_arb_from_list."""
        with open(filename, "r") as f:
            lines = f.readlines()
        data = [float(line.strip()) for line in lines if not line.startswith("#")]
        return self._call("load_arb_from_list", arb_index, arb_name, data)

    def save_display(self, filename: str) -> None:
        raise NotImplementedError(
            "save_display no está expuesto por el puente TCP"
        )

    def _call(self, method, *args, **kwargs):
        req = encode_request(DEVICE_UTG932E, method, args, kwargs)
        last = None
        for attempt in range(3):
            try:
                if attempt:
                    # el WiFi de la Pi tiene power-save: reconectar (con backoff
                    # propio) y reintentar el comando si la conexión ociosa se cayó.
                    self._reconnect()
                return self._send_recv(req)
            except (ConnectionError, TimeoutError, OSError) as e:
                last = e
        raise last

    def _send_recv(self, req):
        self._line.send_line(req)
        line = self._line.recv_line()
        if not line:
            raise ConnectionError("El server cerró la conexión")
        try:
            return decode_response(line)
        except RemoteError as e:
            if e.error_type == "UtgError":
                raise UtgError(e.message) from None
            raise

    def _reconnect(self):
        try:
            self._line.close()
        except Exception:
            pass
        self._connect()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def proxy(*args, **kwargs):
            return self._call(name, *args, **kwargs)

        return proxy
