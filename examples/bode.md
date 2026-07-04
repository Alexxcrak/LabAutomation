# bode.py — Barrido de Bode automatizado

Mide la respuesta en frecuencia (magnitud y fase) de un DUT barriendo una senoidal
con el generador **UTG932E** y midiendo entrada y salida con el osciloscopio **DHO804**.

- **Ganancia** = 20·log10(Vout/Vin) — se mide la entrada **real** (CH del osc), no se
  asume la Vpp del generador → inmune a la carga del cable y a la impedancia de salida.
- **Fase** = `:MEASure:ITEM? RRPHase` de la salida respecto de la entrada.
- Genera un **CSV** (freq, Vin, Vout, ganancia, fase) y un **PNG** (magnitud + fase).

## Conexionado (¡importante!)

```
Generador CH1 ──► entrada del DUT ──┬──► Osc CH2  (BNC directo, 1X)   → Vin (referencia)
                                    │
                       salida DUT ──┴ ... ──► Osc CH1 (punta de sonda, 10X) → Vout
```

- **CH1 = salida (sonda 10X)**, **CH2 = entrada (BNC 1X)**. Configurable con `--ch-in/--ch-out/--probe-*`.
- Declarar bien la **relación de sonda** es crítico: si no coincide con la sonda física,
  las amplitudes salen mal por el factor de atenuación.

## Uso

```bash
# Desde la raíz del repo, con el venv. No hace falta PYTHONPATH (el script agrega Libraries/ solo).
venv/bin/python examples/bode.py --fstart 100 --fstop 1e6 --points 50 --vpp 2
```

Requisitos: el **server TCP corriendo en la Pi** (para el generador) y el **osciloscopio
en la red**. Ver [tcp_bridge_arch] en la memoria del proyecto.

## Argumentos

### Barrido (obligatorios)
| flag | qué hace | nota |
|---|---|---|
| `--fstart` | frecuencia inicial (Hz) | el barrido es **logarítmico** |
| `--fstop` | frecuencia final (Hz) | |
| `--points` | cantidad de puntos | ~10–15 por década está bien |
| `--vpp` | amplitud del generador (Vpp) | la curva en dB es independiente del nivel, pero elegila para **no saturar el DUT** ni quedar en el ruido |

### Amplitud dependiente de la frecuencia
| flag | qué hace | nota |
|---|---|---|
| `--vpp-hi` | amplitud (Vpp) para f ≥ `--vpp-hi-from` | sube el SNR en la **cola** donde la salida es chica. **No afecta la curva en dB** (se mide Vin en cada punto) |
| `--vpp-hi-from` | frecuencia umbral del boost (def. 1000 Hz) | |

Útil en pasabandas/pasaaltos con ganancia alta: **drive bajo en el pico** (no saturar) y
**alto en la cola** (vencer ruido/feedthrough). No bajar el umbral tanto que el boost
sature cerca del pico.

### Calidad de medición
| flag | qué hace | nota |
|---|---|---|
| `--avg` | tope de **promediado de adquisición** (potencia de 2; `1` desactiva). Def. 16 | reduce el ruido aleatorio ∝ √N y baja el piso de medición. Es **adaptativo** (ver abajo) |
| `--avg-time` | presupuesto de tiempo de promediado por punto (s). Def. 0.5 | el script usa el **máximo avg ≤ `--avg`** que entre en este tiempo: poco en baja frecuencia (lento, señal grande), mucho en alta (adquisiciones rápidas, gratis) |
| `--nread` | lecturas por punto para tomar la **mediana**. Def. 3 | rechaza glitches de `RRPHase`. **Ojo**: en baja frecuencia los gaps entre lecturas escalan con el período → usar `--nread 1` si barrés por debajo de ~2 Hz |
| `--settle` | tiempo de asentamiento **mínimo** por punto (s). Def. 0.2 | **SUBILO** si el DUT tiene caps grandes (constante de tiempo lenta). Ej.: cap de 330 µF con polo en 0.5 Hz → τ ≈ 0.32 s → usar `--settle 3` o `4` |

### Conexionado / canales
| flag | def | qué hace |
|---|---|---|
| `--gen-channel` | 1 | canal del generador |
| `--ch-in` | 2 | canal del osc. para la entrada/referencia |
| `--ch-out` | 1 | canal del osc. para la salida del DUT |
| `--probe-in` | 1 | relación de sonda del canal de entrada (1X) |
| `--probe-out` | 10 | relación de sonda del canal de salida (10X) |

### Red
| flag | def | qué hace |
|---|---|---|
| `--scope-ip` | 192.168.68.68 | IP del osciloscopio |
| `--scope-adb-port` | 55555 | puerto ADB del osc. (capturas / autoset) |
| `--gen-host` | env `LAB_HOST` o 192.168.68.108 | host del puente TCP del generador (la Pi) |
| `--gen-port` | 5555 | puerto del puente TCP |

### Salida
| flag | qué hace |
|---|---|
| `--csv` | archivo CSV de salida (def. `bode_<timestamp>.csv`) |
| `--png` | archivo PNG de salida (def. `bode_<timestamp>.png`) |
| `--no-show` | no abrir la ventana del gráfico (para correr headless o scripteado) |

## Cómo funciona (resumen, para no excavar el código)

- **Auto-escala vertical** (`autorange`): por punto ajusta los V/div de cada canal para
  llenar ~6 divisiones. VPP inválido del Rigol = señal **fuera de pantalla** → aleja (sube
  V/div). Maneja señales de mV a decenas de V.
- **Timebase adaptativo**: pone ~4 períodos en pantalla en cada frecuencia.
- **Trigger por flanco sobre la entrada**: la entrada es grande y constante → referencia
  firme para la fase y para alinear el promediado.
- **Promediado adaptativo**: ver `--avg` / `--avg-time`.
- **Settle efectivo por punto** = `max(--settle, n_avg × t_adquisición × 1.5)`. En baja
  frecuencia domina el tiempo de adquisición (varios períodos); en alta, `--settle` o el avg.
- **Magnitud por relación** Vout/Vin (Vin medido) → inmune a la amplitud real del generador.

## Recetas (según lo medido en el TP)

```bash
# Pasabajos / general — señal decente en toda la banda, defaults alcanzan
venv/bin/python examples/bode.py --fstart 100 --fstop 500e3 --points 60 --vpp 5

# Filtro con caps grandes (ej. 330 µF, asienta lento) — settle alto, nread 1 por la baja frec.
venv/bin/python examples/bode.py --fstart 0.5 --fstop 100e3 --points 60 --vpp 5 \
  --avg 64 --avg-time 1.0 --nread 1 --settle 4

# Pasabanda con ganancia alta (pico +24 dB) — vpp bajo para no saturar el pico,
# boost de amplitud en la cola, avg fuerte por el ruido amplificado
venv/bin/python examples/bode.py --fstart 0.5 --fstop 10e3 --points 50 --vpp 0.5 \
  --vpp-hi 5 --vpp-hi-from 600 --avg 64 --avg-time 1.0 --nread 1
```

## Limitaciones conocidas

- **Piso de feedthrough (~−37 a −42 dB)**: acople coherente entrada-salida del banco
  (punta / protoboard). El promediado **NO lo baja** (es coherente, no ruido). Aparece como
  meseta o cero falso. Subir el drive en esa zona (`--vpp-hi`) ayuda. Para medir más abajo:
  mejor layout, tierra de punta corta, o medición diferencial.
- **Saturación del DUT**: si la salida supera las rieles, recorta y la magnitud sale
  comprimida (o `nan` si sobre-rangea la auto-escala). Bajá `--vpp`.
- **Baja frecuencia es lenta**: a 0.5 Hz un período son 2 s y se necesitan varios → varios
  segundos por punto. Es física, no overhead.

## Archivos relacionados

- Wrappers de instrumentos: `Libraries/rigol_dho804/dho804/dho804.py`,
  `Libraries/unit_utg932e/utg962.py` (cliente TCP, con keepalive + reconexión).
- Comandos SCPI verificados contra `Docs/DHO800900_ProgrammingGuide_EN.pdf`.
