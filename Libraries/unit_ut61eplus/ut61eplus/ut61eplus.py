"""Cliente TCP del multímetro UT61E+.

La API replica a `UT61EPLUSLocal` (ver ut61eplus_local.py). Los métodos se
delegan al servidor; `takeMeasurement()` retorna un `RemoteMeasurement` con
los mismos atributos que `Measurement`.
"""

import os
import socket

from remote.protocol import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEVICE_UT61EPLUS,
    LineSocket,
    RemoteError,
    encode_request,
    decode_response,
)


class UT61EPLUS:
    def __init__(self, host=None, port=None, timeout=10.0):
        host = host or os.environ.get("LAB_HOST", DEFAULT_HOST)
        port = int(port or os.environ.get("LAB_PORT", DEFAULT_PORT))
        sock = socket.create_connection((host, port), timeout=timeout)
        self._line = LineSocket(sock)

    def close(self) -> None:
        """Cierra solo la conexión TCP; el instrumento en la Pi queda disponible."""
        self._line.close()

    def _call(self, method, *args, **kwargs):
        self._line.send_line(encode_request(DEVICE_UT61EPLUS, method, args, kwargs))
        line = self._line.recv_line()
        try:
            return decode_response(line)
        except RemoteError as e:
            raise RuntimeError(f"{e.error_type}: {e.message}") from None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def proxy(*args, **kwargs):
            return self._call(name, *args, **kwargs)

        return proxy
