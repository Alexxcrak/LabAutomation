from rigol_dho804.dho804 import DHO804
from unit_ut61eplus.ut61eplus import UT61EPLUS
from unit_utg932e.utg962 import Utg962
import time
osciloscopio = DHO804("192.168.68.68","55555")
generador = Utg962()
multimetro = UT61EPLUS()

osciloscopio.connect()
generador.set_sine(int(1),float(10250),float(-5),float(5))
time.sleep(2)
osciloscopio.auto_set()
time.sleep(2)
osciloscopio.take_screenshot()


generador.close()
osciloscopio.close()