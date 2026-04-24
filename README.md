# LabAutomation

Herramientas en Python para automatizar mediciones y pruebas con equipos de laboratorio.

Este repositorio contiene scripts y módulos para controlar instrumentos como generadores de funciones, multímetros digitales y osciloscopios. La mayoría de los ejemplos están escritos para usar PyVISA y otras bibliotecas comunes en entornos de electrónica.

## Instalación

1. Asegúrate de tener Python 3.10 o superior instalado.
2. Instala las dependencias principales:

```bash
pip install -r requirements.txt
```

Algunos submódulos incluyen sus propios archivos `requirements.txt` para dependencias adicionales.

## Estructura del repositorio

```
Libraries/
├── rigol_dho804/dho804/        # osciloscopio Rigol DHO804 (SCPI por TCPIP + ADB)
├── unit_ut61eplus/ut61eplus/   # multímetro UNI-T UT61E+ (USB HID, chip CP2110)
└── unit_utg932e/               # generador UNI-T UTG932E/UTG962E (PyVISA USB)
examples/                        # scripts de medición que usan los wrappers
```

Cada wrapper expone una clase principal (`DHO804`, `UT61EPLUS`, `Utg962`). Algunos subdirectorios contienen su propio `Examples/` con usos específicos del instrumento.

## Uso rápido

Los ejemplos de la carpeta `examples/` importan los wrappers con rutas relativas a `Libraries/`, así que hay que agregar esa carpeta al `PYTHONPATH`:

```bash
export PYTHONPATH="$PWD/Libraries"
python examples/leer_valor.py
```

El patrón de import es consistente entre los tres wrappers:

```python
from rigol_dho804.dho804 import DHO804
from unit_ut61eplus.ut61eplus import UT61EPLUS
from unit_utg932e.utg962 import Utg962
```

## Requisitos de hardware

Los scripts están pensados para ser ejecutados junto a los equipos mencionados. Es necesario contar con controladores USB/VISA apropiados (por ejemplo, PyVISA‑py o NI-VISA) y, en algunos casos, con `adb` instalado.

## Licencia

Revisa los archivos individuales para condiciones específicas. Parte del código en `unit_ut61eplus/from_vendor` proviene de una aplicación descompilada y puede tener restricciones adicionales.

