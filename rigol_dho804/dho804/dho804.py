import subprocess
from datetime import datetime
import pyvisa

class AdbBridge:
    def __init__(self, ip_puerto):
        self.ip_puerto = ip_puerto

    def conectar(self):
        """Conecta ADB al dispositivo."""
        print(f"[ADB] Conectando a {self.ip_puerto}...")
        resultado = subprocess.run(["adb", "connect", self.ip_puerto], capture_output=True, text=True)
        print(resultado.stdout.strip())

    def tomar_captura(self, nombre_archivo=None):
        """Toma una captura de pantalla del dispositivo."""
        if not nombre_archivo:
            nombre_archivo = datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")

        print(f"[ADB] Tomando captura y guardando como {nombre_archivo}...")
        with open(nombre_archivo, "wb") as f:
            subprocess.run(["adb", "-s", self.ip_puerto, "exec-out", "screencap", "-p"], stdout=f)

    def esta_conectado(self):
        """Verifica si el dispositivo sigue conectado."""
        resultado = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        return self.ip_puerto.split(":")[0] in resultado.stdout

    def touch_center(self):
        subprocess.run(["adb", "shell", "input", "tap", str(512), str(300)])
        
    def adb_disconnect(self):
        subprocess.run(["adb", "disconnect", self.ip_puerto], capture_output=True, text=True)

class DHO804:
    def __init__(self,ip,adbport):
        self.ip = ip
        self.adb_bridge = AdbBridge(ip + ':' + adbport)
        self.rm = pyvisa.ResourceManager()    

    def connect(self):
        """Conecta interfaz ADB y SPCI"""
        self.adb_bridge.conectar()
        self.scpi_bridge = self.rm.open_resource(f'TCPIP::{self.ip}::INSTR')
        self.scpi_bridge.write_termination = '\n'
        self.scpi_bridge.read_termination = '\n'

    def take_screenshot(self):
        if (self.adb_bridge.esta_conectado()):
            self.adb_bridge.tomar_captura()
        else:
            return 0

    def auto_set(self):
        self.scpi_bridge.write(":AUToset")
        self.adb_bridge.touch_center()

    def measure_avg(self, ch: int):
        if(self._validate_channel):
            return float(self.scpi_bridge.query(f':MEASure:VAVG? CHANnel{ch}'))
        else:
            pass
    
    def measure_amp(self, ch: int):
        if(self._validate_channel):
            return float(self.scpi_bridge.query(f':MEASure:VAMP? CHANnel{ch}'))
        else:
            pass
    def measure_rms(self, ch: int):
        if(self._validate_channel):
            return float(self.scpi_bridge.query(f':MEASure:VRMS? CHANnel{ch}'))
        else:
            pass

    def _validate_channel(self,ch:int):
        return (ch > 0 and ch <=5)

    def close(self):
        self.scpi_bridge.close()
        self.rm.close()
        self.adb_bridge.adb_disconnect()
