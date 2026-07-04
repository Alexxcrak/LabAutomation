"""Diagrama de Bode (magnitud y fase) con el generador UTG932E y el osciloscopio DHO804.

El generador inyecta una senoidal de frecuencia variable en la entrada del DUT.
El osciloscopio mide la salida (CH1, sonda 10X) y la entrada (CH2, BNC 1X):

    Ganancia(dB) = 20 * log10(Vout_pp / Vin_pp)
    Fase(deg)    = fase de CH1 (salida) respecto de CH2 (entrada)  (:MEASure:ITEM? RRPHase)

Se mide la entrada real en CH2 (no se asume la Vpp del generador) para que el
resultado sea inmune a la carga del cable y al divisor de salida del generador.

Conexionado:
    Generador CH1  -->  entrada del DUT  +  osciloscopio CH2 (BNC directo, 1X)
    salida del DUT -->  osciloscopio CH1 (punta de sonda, 10X)

Uso (con el venv del proyecto, sin tocar PYTHONPATH):
    venv/bin/python examples/bode.py --fstart 10 --fstop 1e6 --points 50 --vpp 2

Referencia completa de argumentos, recetas por tipo de filtro y limitaciones:
ver examples/bode.md (o `--help` para el resumen).
"""

import argparse
import csv
import math
import os
import statistics
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Libraries"))

import numpy as np
import matplotlib.pyplot as plt

from rigol_dho804.dho804 import DHO804
from unit_utg932e.utg962 import Utg962

# Geometría de pantalla y límites del DHO800 (sonda 1X)
H_DIVS = 10
V_DIVS = 8
V_SCALE_MIN = 500e-6   # V/div
V_SCALE_MAX = 10.0     # V/div
TB_MIN = 2e-9          # s/div
TB_MAX = 1000.0        # s/div
PERIODS_ON_SCREEN = 4  # periodos visibles -> buen compromiso amplitud/fase
INVALID = 1e30         # el Rigol devuelve ~9.9E37 cuando la medición no es válida


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def valid(v):
    return v is not None and v < INVALID


def med(vals):
    """Mediana de las lecturas válidas (descarta outliers), o nan si no hay ninguna."""
    good = [v for v in vals if valid(v)]
    return statistics.median(good) if good else math.nan


def med_phase(vals):
    good = [v for v in vals if valid(v) and abs(v) <= 360]
    return statistics.median(good) if good else math.nan


def pow2_floor(x):
    """Mayor potencia de 2 <= x (mínimo 1)."""
    n = 1
    while n * 2 <= x:
        n *= 2
    return n


def autorange(scope, ch, settle, probe):
    """Ajusta la escala vertical del canal para llenar ~6 divisiones.

    Devuelve la Vpp medida (o nan si la señal no es legible). El llamador ya debe
    haber dado tiempo de estabilización tras el cambio de frecuencia, así que la
    primera medición se hace de una; solo se espera (settle) DESPUÉS de cada cambio
    de escala, para que la traza se acomode antes de re-medir. Cuando el canal ya
    está bien escalado converge sin dormir: en un barrido la entrada de amplitud
    constante cuesta una sola medición por punto.
    Los límites de escala se multiplican por la relación de sonda: la SCALe del
    Rigol queda en amplitud real (entrada x sonda), igual que la medición.
    """
    vmin, vmax = V_SCALE_MIN * probe, V_SCALE_MAX * probe
    vpp = math.nan
    for _ in range(5):
        raw = scope.measure_vpp(ch)
        cur = scope.get_channel_scale(ch)
        if not valid(raw):
            # VPP inválido en el Rigol = señal fuera de pantalla (over-range):
            # hay que ALEJAR (subir V/div). Una señal genuinamente chica devuelve
            # un VPP válido pequeño y cae en la otra rama, así que no se confunden.
            new = min(cur * 5.0, vmax)
            vpp = math.nan
        else:
            vpp = raw
            target = clamp(raw / (0.75 * V_DIVS), vmin, vmax)
            if 0.6 * cur <= target <= 1.3 * cur:
                return vpp                       # ya está bien escalado
            new = target
        if cur <= 0 or abs(new - cur) / cur < 0.02:
            return vpp                           # tope del rango, no se puede mejorar
        scope.set_channel_scale(ch, new)
        time.sleep(settle)                       # dar tiempo a que la traza se acomode
    return vpp


def main():
    p = argparse.ArgumentParser(description="Diagrama de Bode con UTG932E + DHO804")
    p.add_argument("--fstart", type=float, required=True, help="Frecuencia inicial (Hz)")
    p.add_argument("--fstop", type=float, required=True, help="Frecuencia final (Hz)")
    p.add_argument("--points", type=int, required=True, help="Cantidad de puntos")
    p.add_argument("--vpp", type=float, required=True, help="Amplitud del generador (Vpp)")
    p.add_argument("--vpp-hi", type=float, default=None, help="Amplitud Vpp para f>=--vpp-hi-from (sube SNR en la cola de alta frecuencia sin afectar la curva en dB)")
    p.add_argument("--vpp-hi-from", type=float, default=1000.0, help="Frecuencia (Hz) desde la cual usar --vpp-hi (def. 1000)")
    p.add_argument("--gen-channel", type=int, default=1, help="Canal del generador (def. 1)")
    p.add_argument("--ch-in", type=int, default=2, help="Canal osc. de entrada/referencia (def. 2, BNC directo)")
    p.add_argument("--ch-out", type=int, default=1, help="Canal osc. de salida del DUT (def. 1, sonda)")
    p.add_argument("--trig-ch", type=int, default=None, help="Canal del osc. para el disparo (def. = --ch-in). Con entrada muy chica/ruidosa, disparar sobre la salida (grande y estable): --trig-ch = --ch-out")
    p.add_argument("--vin-ref", type=float, default=None, help="Amplitud de entrada conocida (Vpp) como referencia fija en vez de medir Vin. Se mide SOLO la salida (--ch-out) y el canal de trigger se usa solo para disparar (p.ej. la salida SYNC del generador, se AC-acopla). Gain = 20log10(Vout/Vin-ref)")
    p.add_argument("--probe-in", type=float, default=1, help="Relación de sonda del canal de entrada (def. 1X)")
    p.add_argument("--probe-out", type=float, default=10, help="Relación de sonda del canal de salida (def. 10X)")
    p.add_argument("--scope-ip", default="192.168.68.68", help="IP del osciloscopio")
    p.add_argument("--scope-adb-port", default="55555", help="Puerto ADB del osciloscopio")
    p.add_argument("--gen-host", default=None, help="Host del puente TCP del generador")
    p.add_argument("--gen-port", default=None, help="Puerto del puente TCP del generador")
    p.add_argument("--gen-local", action="store_true", help="Generador por USB directo (pyvisa/USBTMC), sin Pi. Ignora --gen-host/--gen-port")
    p.add_argument("--avg", type=int, default=16, help="Tope de promediado de adquisición (potencia de 2; 1=desactiva). Adaptativo: usa el máximo que entre en --avg-time por punto")
    p.add_argument("--avg-time", type=float, default=0.5, help="Presupuesto de tiempo de promediado por punto (s)")
    p.add_argument("--nread", type=int, default=3, help="Lecturas por punto para tomar la mediana (def. 3)")
    p.add_argument("--settle", type=float, default=0.2, help="Tiempo de asentamiento mínimo (s)")
    p.add_argument("--csv", default=None, help="Archivo CSV de salida")
    p.add_argument("--append", action="store_true", help="Agrega las filas a un CSV existente en vez de sobrescribir (no reescribe el encabezado). Útil para extender un barrido a otro rango de frecuencias. El PNG de la corrida solo refleja estos puntos nuevos")
    p.add_argument("--png", default=None, help="Archivo PNG de salida")
    p.add_argument("--no-show", action="store_true", help="No abrir la ventana del gráfico")
    args = p.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = args.csv or f"bode_{stamp}.csv"
    png_path = args.png or f"bode_{stamp}.png"

    freqs = np.logspace(math.log10(args.fstart), math.log10(args.fstop), args.points)

    if args.gen_local:
        from unit_utg932e.utg962_local import Utg962Local
        gen = Utg962Local()
    else:
        gen = Utg962(host=args.gen_host, port=args.gen_port)
    scope = DHO804(args.scope_ip, args.scope_adb_port)
    scope.connect()

    results = []
    try:
        # Preparar osciloscopio: relación de sonda, canales visibles, centrados y
        # una escala inicial razonable suponiendo ganancia ~1. En modo --vin-ref se
        # prepara solo la salida (la entrada no se mide) más el canal de trigger.
        trig_ch = args.trig_ch or args.ch_in
        setup_chs = ((args.ch_out, args.probe_out),) if args.vin_ref is not None \
            else ((args.ch_in, args.probe_in), (args.ch_out, args.probe_out))
        for ch, probe in setup_chs:
            scope.set_channel_probe(ch, probe)
            scope.set_channel_display(ch, True)
            scope.set_channel_offset(ch, 0.0)
            scope.set_channel_scale(
                ch, clamp(args.vpp / (0.75 * V_DIVS), V_SCALE_MIN * probe, V_SCALE_MAX * probe))
        if args.vin_ref is not None:
            # El canal de trigger (SYNC del generador) se usa solo para disparar. Se
            # AC-acopla para centrar la cuadrada TTL en 0 (dispara a nivel 0 sin
            # importar si es 3.3V o 5V) y se autoescala una sola vez: su amplitud es
            # constante con la frecuencia.
            scope.set_channel_probe(trig_ch, args.probe_in)
            scope.set_channel_display(trig_ch, True)
            scope.set_channel_offset(trig_ch, 0.0)
            scope.set_channel_coupling(trig_ch, "AC")
            scope.set_channel_scale(trig_ch, 1.0 * args.probe_in)  # ~TTL en pantalla
            time.sleep(args.settle)
            autorange(scope, trig_ch, args.settle, args.probe_in)
        # Disparo sobre la entrada (señal grande y constante): referencia firme
        # para alinear el promediado y medir la fase. El promediado se ajusta por
        # punto (ver el lazo): poco en baja frec. (lento, señal fuerte) y mucho en
        # alta frec. (adquisiciones rápidas, señal chica) para limpiar la onda.
        scope.set_trigger_edge(trig_ch, level=0.0)
        last_avg = None

        write_header = not (args.append and os.path.exists(csv_path) and os.path.getsize(csv_path) > 0)
        with open(csv_path, "a" if args.append else "w", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["Freq_Hz", "Vin_Vpp", "Vout_Vpp", "Gain_dB", "Phase_deg"])
            print(f"{'Freq[Hz]':>12} {'Vin[Vpp]':>10} {'Vout[Vpp]':>10} {'Gain[dB]':>10} {'Phase[deg]':>11} {'avg':>5}")

            for f_hz in freqs:
                # Drive dependiente de la frecuencia: más amplitud en la cola de
                # alta frecuencia (ganancia baja → salida chica) para vencer el ruido.
                # La curva en dB no cambia porque medimos Vin en cada punto.
                amp = args.vpp_hi if (args.vpp_hi is not None and f_hz >= args.vpp_hi_from) else args.vpp
                gen.set_sine(args.gen_channel, float(f_hz), -amp / 2.0, amp / 2.0)

                screen_t = PERIODS_ON_SCREEN / f_hz
                scope.set_timebase(clamp(screen_t / H_DIVS, TB_MIN, TB_MAX))
                acq_t = max(screen_t, 0.004)          # ~tiempo por adquisición (piso por overhead)
                # Promediado adaptativo: el máximo (potencia de 2, tope args.avg)
                # que entre en el presupuesto de tiempo. Cambiar el avg resetea el
                # buffer, así que solo se reescribe cuando cambia.
                n_avg = max(1, min(args.avg, pow2_floor(args.avg_time / acq_t))) if args.avg > 1 else 1
                if n_avg != last_avg:
                    scope.set_acquire_average(n_avg)
                    last_avg = n_avg
                settle = max(args.settle, n_avg * acq_t * 1.5)

                # Estabilización tras cambiar frecuencia/timebase. El generador es
                # DDS (reajusta al instante); este tiempo es para que el DUT llegue a
                # régimen y para que el promediado del osciloscopio reconverja con N
                # adquisiciones nuevas a la nueva base de tiempo.
                time.sleep(settle)

                # autorange solo fija la escala vertical (su settle reconverge el
                # promediado tras cada cambio de escala). El canal de trigger no se
                # reescala por punto: su amplitud es constante (ver setup).
                if args.vin_ref is None:
                    autorange(scope, args.ch_in, settle, args.probe_in)
                autorange(scope, args.ch_out, settle, args.probe_out)

                # Mediana de varias lecturas sobre la onda ya promediada: rechaza
                # algún glitch residual de RRPHase. Espaciamos las lecturas un par
                # de adquisiciones para que el promedio corriente evolucione.
                if args.vin_ref is not None:
                    # Referencia fija: se mide solo la salida; la entrada es conocida.
                    rv_out = []
                    for i in range(args.nread):
                        rv_out.append(scope.measure_vpp(args.ch_out))
                        if i < args.nread - 1:
                            time.sleep(2 * acq_t)
                    vin, vout, phase = args.vin_ref, med(rv_out), math.nan
                else:
                    rv_in, rv_out, rph = [], [], []
                    for i in range(args.nread):
                        rv_in.append(scope.measure_vpp(args.ch_in))
                        rv_out.append(scope.measure_vpp(args.ch_out))
                        rph.append(scope.measure_phase(args.ch_out, args.ch_in))
                        if i < args.nread - 1:
                            time.sleep(2 * acq_t)
                    vin, vout, phase = med(rv_in), med(rv_out), med_phase(rph)

                gain = (20.0 * math.log10(vout / vin)
                        if valid(vin) and valid(vout) and vin > 0 and vout > 0
                        else math.nan)

                writer.writerow([f"{f_hz:.4f}", f"{vin:.6f}", f"{vout:.6f}",
                                 f"{gain:.3f}", f"{phase:.3f}"])
                f.flush()
                results.append((f_hz, gain, phase))
                print(f"{f_hz:12.2f} {vin:10.4f} {vout:10.4f} {gain:10.3f} {phase:11.3f} {n_avg:5d}")
    finally:
        gen.set_output(args.gen_channel, False)
        gen.close()
        scope.set_acquire_average(1)   # volver a modo NORMal
        if args.vin_ref is not None:
            scope.set_channel_coupling(args.trig_ch or args.ch_in, "DC")  # restaurar acople
        scope.close()

    # Gráfico
    fr = np.array([r[0] for r in results])
    mag = np.array([r[1] for r in results])
    ph = np.array([r[2] for r in results])

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(9, 7))
    ax1.semilogx(fr, mag, "-o", markersize=3)
    ax1.set_ylabel("Magnitud [dB]")
    ax1.set_title(f"Diagrama de Bode  ({args.vpp} Vpp, {args.points} puntos)")
    ax1.grid(True, which="both", ls=":")

    ax2.semilogx(fr, ph, "-o", markersize=3, color="tab:orange")
    ax2.set_ylabel("Fase [°]")
    ax2.set_xlabel("Frecuencia [Hz]")
    ax2.grid(True, which="both", ls=":")

    fig.tight_layout()
    fig.savefig(png_path, dpi=120)
    print(f"\nCSV:  {csv_path}\nPNG:  {png_path}")
    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
