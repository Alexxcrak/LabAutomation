from unit_ut61eplus.ut61eplus import UT61EPLUS

def main():
    multimetro = UT61EPLUS()
    medicion = multimetro.takeMeasurement()

    if medicion is None:
        print("No se pudo leer la medición.")
        return

    print(f"{medicion.value} {medicion.unit}")

if __name__ == "__main__":
    main()
