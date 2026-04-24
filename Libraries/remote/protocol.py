"""Protocolo JSON line-delimited para el puente TCP de instrumentos.

Request:  {"device": "...", "method": "...", "args": [...], "kwargs": {...}}
Response: {"ok": true, "result": <...>} | {"ok": false, "error": "...", "message": "..."}

Valores con tipos no-JSON (Decimal, bytes) se envuelven con {"__type__": "...", ...}
para que el cliente los pueda reconstruir.
"""

import decimal
import json


DEFAULT_HOST = "192.168.68.115"
DEFAULT_PORT = 5555

DEVICE_UTG932E = "utg932e"
DEVICE_UT61EPLUS = "ut61eplus"


def _encode(obj):
    if isinstance(obj, decimal.Decimal):
        return {"__type__": "decimal", "value": str(obj)}
    if isinstance(obj, decimal.Overflow):
        return {"__type__": "decimal_overflow"}
    if isinstance(obj, (bytes, bytearray)):
        return {"__type__": "bytes", "value": bytes(obj).hex()}
    if hasattr(obj, "_data") and hasattr(obj, "mode"):
        # Mediciones del UT61E+: serializamos todas las keys del _data
        return {
            "__type__": "measurement",
            "data": {k: _encode(v) for k, v in obj._data.items()},
        }
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_encode(x) for x in obj]
    return obj


def _decode(obj):
    if isinstance(obj, dict):
        t = obj.get("__type__")
        if t == "decimal":
            return decimal.Decimal(obj["value"])
        if t == "decimal_overflow":
            return decimal.Overflow()
        if t == "bytes":
            return bytes.fromhex(obj["value"])
        if t == "measurement":
            return RemoteMeasurement({k: _decode(v) for k, v in obj["data"].items()})
        return {k: _decode(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode(x) for x in obj]
    return obj


class RemoteError(Exception):
    """Excepción genérica que envuelve errores del servidor."""

    def __init__(self, error_type, message):
        super().__init__(f"{error_type}: {message}")
        self.error_type = error_type
        self.message = message


class RemoteMeasurement:
    """Espejo de Measurement del lado cliente.

    Expone los mismos atributos/properties que ut61eplus_local.Measurement
    pero sin dependencia de `hid`. Los datos vienen ya parseados desde el servidor.
    """

    def __init__(self, data):
        self._data = data

    @property
    def binary(self): return self._data.get("binary")
    @property
    def mode(self): return self._data["mode"]
    @property
    def range(self): return self._data["range"]
    @property
    def display(self): return self._data["display"]
    @property
    def overload(self): return self._data["overload"]
    @property
    def display_decimal(self): return self._data["display_decimal"]
    @property
    def display_unit(self): return self._data["display_unit"]
    @property
    def unit(self): return self._data["unit"]
    @property
    def value(self): return self._data["decimal"]
    @property
    def progress(self): return self._data["progres"]
    @property
    def isMax(self): return self._data["max"]
    @property
    def isMin(self): return self._data["min"]
    @property
    def isHold(self): return self._data["hold"]
    @property
    def isRel(self): return self._data["rel"]
    @property
    def isAuto(self): return self._data["auto"]
    @property
    def hasBatteryWarning(self): return self._data["battery"]
    @property
    def hasHVWarning(self): return self._data["hvwarning"]
    @property
    def isDC(self): return self._data["dc"]
    @property
    def isMaxPeak(self): return self._data["peak_max"]
    @property
    def isMinPeak(self): return self._data["peak_min"]

    def __str__(self):
        return f"<RemoteMeasurement {self.mode} {self.display} {self.display_unit}>"


def encode_request(device, method, args=(), kwargs=None):
    payload = {
        "device": device,
        "method": method,
        "args": _encode(list(args)),
        "kwargs": _encode(kwargs or {}),
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


def decode_request(line):
    d = json.loads(line)
    return d["device"], d["method"], _decode(d.get("args", [])), _decode(d.get("kwargs", {}))


def encode_ok(result):
    return (json.dumps({"ok": True, "result": _encode(result)}) + "\n").encode("utf-8")


def encode_error(exc):
    return (json.dumps({
        "ok": False,
        "error": type(exc).__name__,
        "message": str(exc),
    }) + "\n").encode("utf-8")


def decode_response(line):
    d = json.loads(line)
    if d["ok"]:
        return _decode(d["result"])
    raise RemoteError(d["error"], d["message"])


class LineSocket:
    """Wrapper sobre socket con envío/recepción de líneas UTF-8 terminadas en \\n."""

    def __init__(self, sock):
        self.sock = sock
        self._buf = b""

    def send_line(self, data: bytes):
        self.sock.sendall(data)

    def recv_line(self) -> bytes:
        while b"\n" not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                if self._buf:
                    raise ConnectionError("Peer closed mid-message")
                return b""
            self._buf += chunk
        line, _, rest = self._buf.partition(b"\n")
        self._buf = rest
        return line

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
