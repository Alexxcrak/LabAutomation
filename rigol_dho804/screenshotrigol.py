from capturador import AdbCapturador  # si lo guardaste como capturador.py

capturador = AdbCapturador("192.168.68.68:55555")
capturador.conectar()

if capturador.esta_conectado():
    capturador.tomar_captura()
else:
    print("No se pudo conectar al dispositivo.")
