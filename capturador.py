import subprocess
from datetime import datetime

class AdbCapturador:
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
