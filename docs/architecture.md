# Arquitectura del Sistema EEG MIDI

## 🏗️ Diagrama de Flujo General

```
┌─────────────────────────────────────────────────────────────────┐
│                    SISTEMA EEG MIDI                             │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────┐         ┌──────────────────────────┐
    │   ARDUINO UNO            │         │   DSP PROCESSOR          │
    │   (Firmware PlatformIO)  │         │   (Python)               │
    └──────────────────────────┘         └──────────────────────────┘
              │                                      │
              │                                      │
    ┌─────────▼─────────┐                ┌─────────▼────────────┐
    │ 1. ADC Interface  │                │ 1. Serial Reader     │
    │   (ADS1299Plus)   │                │    (data_receiver)   │
    └─────────┬─────────┘                └─────────┬────────────┘
              │                                      │
              │                                      │
    ┌─────────▼─────────┐                ┌─────────▼────────────┐
    │ 2. Data Packing   │                │ 2. Data Parser       │
    │   (Binario 36B)   │                │    (struct unpack)   │
    │   [idx + 8xCH]    │                │    (little-endian)   │
    └─────────┬─────────┘                └─────────┬────────────┘
              │                                      │
              │      SERIAL @ 115200 bps             │
              ├─────────────────────────────────────►│
              │       (Raw binary frames)            │
              │                                      │
              │                        ┌─────────────▼────────────┐
              │                        │ 3. Voltage Conversion    │
              │                        │    raw × LSB (2.235e-8)  │
              │                        └─────────────┬────────────┘
              │                                      │
              │                        ┌─────────────▼────────────┐
              │                        │ 4. Signal Processing     │
              │                        │    (signal_processor.py) │
              │                        │  - Filtrado             │
              │                        │  - Análisis espectral   │
              │                        │  - Detección eventos    │
              │                        └─────────────┬────────────┘
              │                                      │
              │                        ┌─────────────▼────────────┐
              │                        │ 5. Output & Control     │
              │                        │  - MIDI Generation      │
              │                        │  - Logging              │
              │                        │  - Real-time Display    │
              │                        └────────────────────────┘
```

## 🔌 Conexiones Físicas

### Arduino ↔ ADS1299

```
Arduino UNO              ADS1299 Plus
├─ Pin 10 (CS)   ────→  CS
├─ Pin 11 (MOSI) ────→  DIN
├─ Pin 12 (MISO) ◄────  DOUT
├─ Pin 13 (SCK)  ────→  CLK
├─ Pin 2 (DRDY)  ◄────  DRDY (Data Ready, active LOW)
├─ Pin 3 (START) ────→  START
├─ Pin 4 (RESET) ────→  RESET
└─ Pin 5 (PWDN)  ────→  PWDN
    
GND ──────────→ GND
```

### Arduino ↔ PC (Serial Communication)

```
Arduino          USB Cable        PC
  ├─ TX (USB) ◄─────────────────────► COM3 (Virtual Serial)
  └─ RX (USB)                    @ 115200 bps
```

### Arduino ↔ DSP Processor (SPI Futuro)

```
Arduino          SPI Cable        DSP Processor
├─ Pin 9 (CS)    ────────────→   CS
├─ Pin 11 (MOSI) ────────────→   MOSI
├─ Pin 12 (MISO) ◄────────────   MISO
├─ Pin 13 (SCK)  ────────────→   SCK
└─ GND           ────────────→   GND
```

## 📊 Especificación de Datos

### Frame Binario (36 bytes, little-endian)

```
┌─────────────┬──────────┬──────────┬─────┬──────────┐
│ sample_idx  │ channel0 │ channel1 │ ... │ channel7 │
│  (4 bytes)  │ (4 bytes)│ (4 bytes)│     │ (4 bytes)│
└─────────────┴──────────┴──────────┴─────┴──────────┘
     Byte 0-3   Byte 4-7   Byte 8-11      Byte 32-35

Tipo de dato: uint32_t (idx) + 8x int32_t (canales)
Codificación: Signed 24-bit → Sign-extended 32-bit
```

### Rangos y Conversión

```
Raw (24-bit)          Int32 (32-bit)         Voltaje
──────────            ──────────────         ───────
+8,388,607            +8,388,607             +0.1876 V
    0                     0                      0 V
-8,388,608            -8,388,608             -0.1876 V

Fórmula: V = raw × 2.235e-8
Rango EEG típico: ±250 µV = ±0.00025 V
```

## 🎯 Componentes Principales

### 1. Arduino Firmware (`arduino-firmware/`)

| Archivo | Función |
|---------|---------|
| `src/main.cpp` | Interfaz ADS1299 + empaquetamiento de datos |
| `lib/ADS1299Plus/` | Driver del ADC (comunicación SPI) |
| `platformio.ini` | Configuración del build (board, COM, libs) |

**Responsabilidades:**
- ✅ Inicializar ADS1299 en modo RDATAC
- ✅ Leer frames cuando DRDY = LOW
- ✅ Empaquetar datos en buffer binario (little-endian)
- ✅ Enviar por Serial a 115200 bps
- ✅ Mostrar voltajes por Serial para debugging

### 2. DSP Processor (`dsp-processor/`)

| Módulo | Función |
|--------|---------|
| `data_receiver.py` | Lectura y parseo del buffer |
| `signal_processor.py` | Filtrado y análisis espectral |
| `main.py` | Orquestador e integración |

**Responsabilidades:**
- ✅ Conectar al Arduino por Serial
- ✅ Leer frames binarios (36 bytes)
- ✅ Parsear datos (little-endian)
- ✅ Convertir a voltaje
- ✅ Aplicar filtros DSP (paso-banda, notch)
- ✅ Análisis espectral (bandas: delta, theta, alpha, beta, gamma)
- ✅ Detección de eventos (futuro: seizure detection, etc.)
- ✅ Generar MIDI (futuro)

## 🔄 Flujo de Datos Detallado

### Transmisión (Arduino → DSP)

```
1. ADS1299 muestrea 8 canales (24-bit cada uno)
   └─ Frecuencia: ~250 Hz

2. DRDY se pone LOW cuando hay datos listos

3. Arduino lee en modo RDATAC:
   - Lee status (1 byte)
   - Lee 8 canales (3 bytes cada uno)
   └─ Total: 25 bytes raw

4. Procesar datos:
   - Sign-extend 24-bit → 32-bit
   - Empaquetar: [sample_idx (4B)][ch0-ch7 (4B cada)]
   - Codificar little-endian

5. Enviar por Serial (115200 bps)
   └─ Frame de 36 bytes

6. DSP recibe en buffer Serial
   └─ Timeout: ~1 seg si no hay datos
```

### Recepción (DSP)

```
1. Leer 36 bytes del buffer Serial

2. Validar integridad:
   - sample_idx incrementa → detecta pérdidas
   - Timeout → reconectar

3. Parsear (struct.unpack, little-endian):
   - sample_idx = unpack('<I', bytes[0:4])
   - channels = unpack('<8i', bytes[4:36])

4. Convertir a voltaje:
   - voltage = raw × 2.235e-8

5. Almacenar en buffer circular (1 segundo de datos)

6. Procesar según demanda:
   - Filtrado
   - FFT/Welch
   - Análisis de bandas
```

## 📈 Rendimiento Esperado

| Métrica | Valor | Notas |
|---------|-------|-------|
| Muestras/segundo | 250 | 1 frame cada 4 ms |
| Bytes/segundo | ~9 KB/s | 36 bytes × 250 Hz |
| Utilización USB | <1% | Virtual COM port |
| Latencia Serial | <5 ms | A 115200 bps |
| Buffer circular | 250 frames | 1 segundo de datos |
| Latencia DSP | <50 ms | Con filtrado + FFT |

## 🧪 Testing

### Simulación (sin Arduino)

```python
# dsp-processor/src/main.py --demo
→ Genera datos sintéticos (10 Hz alpha + ruido)
→ Procesa como si fueran reales
→ Muestra espectro y bandas
```

### Validación de Protocolo

```python
# tests/test_data_receiver.py
→ Verifica parsing de frames
→ Valida conversión little-endian
→ Comprueba rango de voltaje
```

### Monitoreo en Vivo

```bash
# Terminal 1: Monitor Serial (ver datos crudos)
platformio device monitor --port COM3 --baud 115200

# Terminal 2: DSP con debug
python src/main.py --port COM3 --debug
→ Mostrar cada frame parseado
```

## 🚀 Evolución Futura

### Fase 2: SPI para DSP

```
Arduino (Master) ───SPI (1MHz)─→ DSP Processor (Slave)
- Mayor velocidad
- Protocolo con handshake (ACK/NAK)
```

### Fase 3: MIDI Output

```
DSP Processor → MIDI/USB ↔ DAW (Ableton, FL Studio, etc.)
- Trigger de samples por eventos EEG
- Control de parámetros en tiempo real
```

### Fase 4: Machine Learning

```
DSP Processor + TensorFlow Lite
- Clasificación de estados EEG
- Detección de artefactos
- Predicción de convulsiones
```

---

**Última actualización:** Diciembre 2, 2025
**Versión:** 1.0 - Prototype
