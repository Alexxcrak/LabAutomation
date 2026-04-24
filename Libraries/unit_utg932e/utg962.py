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
    def __init__(self, host=None, port=None, timeout=10.0):
        host = host or os.environ.get("LAB_HOST", DEFAULT_HOST)
        port = int(port or os.environ.get("LAB_PORT", DEFAULT_PORT))
        sock = socket.create_connection((host, port), timeout=timeout)
        self._line = LineSocket(sock)

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
        self._line.send_line(encode_request(DEVICE_UTG932E, method, args, kwargs))
        line = self._line.recv_line()
        try:
            return decode_response(line)
        except RemoteError as e:
            if e.error_type == "UtgError":
                raise UtgError(e.message) from None
            raise

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def proxy(*args, **kwargs):
            return self._call(name, *args, **kwargs)

        return proxy
