import time
import pyvisa
import csv
import argparse

# Argumentos de línea de comandos
parser = argparse.ArgumentParser(description='Barrido de curva I-V de un diodo con SCPI')
parser.add_argument('--output', type=str, required=True, help='Nombre del archivo CSV de salida')
parser.add_argument('--vmin', type=float, required=True, help='Tensión mínima del generador (V)')
parser.add_argument('--vmax', type=float, required=True, help='Tensión máxima del generador (V)')
parser.add_argument('--step', type=float, required=True, help='Paso de tensión (V)')
args = parser.parse_args()

# Parámetros
resistencia = 9900  # Ohms
espera = 1  # Tiempo de espera entre pasos (segundos)

# Inicializar VISA
rm = pyvisa.ResourceManager()

# Conexión a los instrumentos
generador = rm.open_resource('USB0::26198::2100::AWG1224410024::0::INSTR')
osciloscopio = rm.open_resource('TCPIP::192.168.68.68::INSTR')

# Configurar terminaciones
generador.write_termination = '\n'
osciloscopio.write_termination = '\n'
osciloscopio.read_termination = '\n'

# Inicializar generador
generador.write(':CHANnel1:BASE:WAVe DC')
generador.write(':CHANnel1:OUTPut 1')

# Crear y abrir archivo CSV
with open(args.output, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["V_generador (V)", "V_diodo (V)", "Corriente (A)"])

    # Bucle de barrido
    offset = args.vmin
    while offset <= args.vmax:
        generador.write(f':CHANnel1:BASE:OFFSet {offset:.3f}')
        time.sleep(espera)

        try:
            Vg = float(osciloscopio.query(':MEASure:VAVG? CHANnel1'))
            Vr = float(osciloscopio.query(':MEASure:VAVG? CHANnel2'))
            Vd = Vg - Vr
            I = Vr / resistencia
            writer.writerow([f"{Vg:.5f}", f"{Vd:.5f}", f"{I:.9f}"])
            print(f"{Vg:.5f} V | {Vd:.5f} V | {I:.9f} A")
        except Exception as e:
            print(f"Error en offset {offset:.3f} V: {e}")

        offset += args.step

# Apagar salida del generador
generador.write(':CHANnel1:OUTPut 0')

# Cerrar instrumentos
generador.close()
osciloscopio.close()
rm.close()
