import subprocess
import time
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
        """Conecta interfaz ADB y SCPI.

        Reintenta el open VXI-11: el WiFi del osciloscopio tiene power-save y la
        radio puede estar dormida en el momento de conectar. El timeout VISA
        generoso tolera los despertares de radio durante el barrido.
        """
        self.adb_bridge.conectar()
        last = None
        for attempt in range(4):
            try:
                self.scpi_bridge = self.rm.open_resource(
                    f'TCPIP::{self.ip}::INSTR', open_timeout=8000)
                self.scpi_bridge.write_termination = '\n'
                self.scpi_bridge.read_termination = '\n'
                self.scpi_bridge.timeout = 8000
                return
            except Exception as e:
                last = e
                time.sleep(1.5)
        raise last

    def take_screenshot(self):
        if (self.adb_bridge.esta_conectado()):
            self.adb_bridge.tomar_captura()
        else:
            return 0

    def auto_set(self):
        self.scpi_bridge.write(":AUToset")
        self.adb_bridge.touch_center()

    def measure_avg(self, ch: int):
        if self._validate_channel(ch):
            return float(self.scpi_bridge.query(f':MEASure:VAVG? CHANnel{ch}'))
        else:
            pass

    def measure_amp(self, ch: int):
        if self._validate_channel(ch):
            return float(self.scpi_bridge.query(f':MEASure:VAMP? CHANnel{ch}'))
        else:
            pass
    def measure_rms(self, ch: int):
        if self._validate_channel(ch):
            return float(self.scpi_bridge.query(f':MEASure:VRMS? CHANnel{ch}'))
        else:
            pass

    def measure_vpp(self, ch: int):
        if self._validate_channel(ch):
            return float(self.scpi_bridge.query(f':MEASure:VPP? CHANnel{ch}'))

    def measure_phase(self, ch_a: int, ch_b: int):
        """Fase de ch_a respecto de ch_b en grados (flanco de subida vs subida)."""
        if self._validate_channel(ch_a) and self._validate_channel(ch_b):
            return float(self.scpi_bridge.query(
                f':MEASure:ITEM? RRPHase,CHANnel{ch_a},CHANnel{ch_b}'))

    def set_channel_display(self, ch: int, on: bool):
        if self._validate_channel(ch):
            self.scpi_bridge.write(f':CHANnel{ch}:DISPlay {"ON" if on else "OFF"}')

    def set_channel_scale(self, ch: int, scale: float):
        """Escala vertical en V/div."""
        if self._validate_channel(ch):
            self.scpi_bridge.write(f':CHANnel{ch}:SCALe {scale}')

    def get_channel_scale(self, ch: int):
        if self._validate_channel(ch):
            return float(self.scpi_bridge.query(f':CHANnel{ch}:SCALe?'))

    def set_channel_offset(self, ch: int, offset: float):
        """Offset vertical en V."""
        if self._validate_channel(ch):
            self.scpi_bridge.write(f':CHANnel{ch}:OFFSet {offset}')

    def set_channel_coupling(self, ch: int, coupling: str):
        """Acople de entrada del canal: AC, DC o GND."""
        if self._validate_channel(ch):
            self.scpi_bridge.write(f':CHANnel{ch}:COUPling {coupling}')

    def set_channel_probe(self, ch: int, ratio: float):
        """Relación de atenuación de la sonda (p.ej. 1 o 10).

        El DHO800 valida PROBe contra una lista discreta con match estricto:
        acepta "1"/"10" pero rechaza "1.0"/"10.0" (-222 Data out of range). Se
        formatea con :g para colapsar el .0 de los enteros sin romper los ratios
        fraccionarios (0.1, 0.001).
        """
        if self._validate_channel(ch):
            self.scpi_bridge.write(f':CHANnel{ch}:PROBe {ratio:g}')

    def set_timebase(self, scale: float):
        """Escala horizontal (base de tiempo principal) en s/div."""
        self.scpi_bridge.write(f':TIMebase:MAIN:SCALe {scale}')

    def set_acquire_average(self, count: int):
        """Promediado de adquisición (count = potencia de 2). count<=1 -> NORMal."""
        if count and count > 1:
            self.scpi_bridge.write(':ACQuire:TYPE AVERages')
            self.scpi_bridge.write(f':ACQuire:AVERages {count}')
        else:
            self.scpi_bridge.write(':ACQuire:TYPE NORMal')

    def set_trigger_edge(self, source: int, level: float = 0.0, slope: str = "POSitive"):
        """Trigger por flanco sobre un canal: referencia estable para promediar y fase."""
        if self._validate_channel(source):
            self.scpi_bridge.write(':TRIGger:MODE EDGE')
            self.scpi_bridge.write(':TRIGger:SWEep AUTO')
            self.scpi_bridge.write(f':TRIGger:EDGE:SOURce CHANnel{source}')
            self.scpi_bridge.write(f':TRIGger:EDGE:SLOPe {slope}')
            self.scpi_bridge.write(f':TRIGger:EDGE:LEVel {level}')

    def _validate_channel(self,ch:int):
        return (ch > 0 and ch <=5)

    def close(self):
        self.scpi_bridge.close()
        self.rm.close()
        self.adb_bridge.adb_disconnect()
