from rigol_dho804.dho804 import DHO804
from unit_ut61eplus.ut61eplus import UT61EPLUS
from unit_utg932e.utg962 import Utg962
from time import sleep
import matplotlib.pyplot as plt
import csv
import numpy as np

#osciloscopio = DHO804("192.168.68.68","55555")
generador = Utg962()
multimetro = UT61EPLUS()

#osciloscopio.connect()
generador.set_dc(1, 0)
generador.set_output(1, 1)
with open("mediciones.csv", mode="w", newline="") as file:
    writer = csv.writer(file)
    
    # cabecera
    writer.writerow(["Vdd","Vds", "Current[mA]"])
    print("Vdd","Vds", "Current[mA]")
    for x in np.arange(0, 4.01, 0.1):
        x = round(x, 2)
        
        # tus sentencias de medición
        generador.set_dc(1, x)
        sleep(5)
        Vr = float(multimetro.takeMeasurement().value)
        current = Vr 
        Vds = x - Vr

        # guardar fila en CSV
        writer.writerow([x,f"{Vds:.3f}", f"{current:.3f}"])
        print(f"{x} {Vds:.3f} {current:.3f}")
        sleep(2)

generador.set_dc(1, 0)
generador.set_output(1,0)
#generador.set_output(2,0)
generador.close()
#osciloscopio.close()