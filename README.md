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

- **capturador.py** – clase para realizar capturas de pantalla en un dispositivo Android mediante ADB.
- **diodetracer.py** – realiza un barrido de tensión en un diodo y guarda la curva I-V en CSV utilizando comandos SCPI.
- **instrumentos.py** – muestra los dispositivos detectados por PyVISA.
- **leer_valor.py** – ejemplo básico para leer una medida del multímetro UT61E+.
- **rigol_dho804/** – scripts relacionados con el osciloscopio Rigol DHO804 (ej. `screenshotrigol.py`).
- **unit_ut61eplus/** – módulo para comunicarse con el multímetro UNI-T UT61E+ y utilidades asociadas.
- **unit_utg932e/** – implementa controles para el generador de funciones UNI-T UTG932E/UTG962E.

Cada carpeta contiene ejemplos y, en algunos casos, un README específico con más detalles.

## Uso rápido

Consulta los README de cada subdirectorio para instrucciones específicas. Por ejemplo, para capturar un valor con el multímetro UT61E+:

```bash
python leer_valor.py
```

Para trazar la curva de un diodo:

```bash
python diodetracer.py --output medicion.csv --vmin 0 --vmax 1 --step 0.05
```

## Requisitos de hardware

Los scripts están pensados para ser ejecutados junto a los equipos mencionados. Es necesario contar con controladores USB/VISA apropiados (por ejemplo, PyVISA‑py o NI-VISA) y, en algunos casos, con `adb` instalado.

## Licencia

Revisa los archivos individuales para condiciones específicas. Parte del código en `unit_ut61eplus/from_vendor` proviene de una aplicación descompilada y puede tener restricciones adicionales.

