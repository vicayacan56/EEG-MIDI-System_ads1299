# EEG MIDI System - Dual Architecture

Sistema de adquisición y procesamiento de señales EEG en tiempo real usando Arduino + Procesador DSP.

## 🏗️ Arquitectura

```
EEG-MIDI-System/
├── arduino-firmware/          # PlatformIO - Firmware para Arduino UNO
│   ├── src/main.cpp          # Interfaz con ADS1299 + envío de datos
│   ├── lib/                  # Librerías (ADS1299Plus, SafeSPI)
│   └── platformio.ini
│
├── dsp-processor/            # Python - Procesamiento DSP en tiempo real
│   ├── src/
│   │   ├── data_receiver.py      # Lectura del buffer Serial/SPI
│   │   ├── signal_processor.py   # Procesamiento de señal
│   │   └── main.py               # Orquestador principal
│   ├── tests/                    # Unit tests
│   └── requirements.txt
│
└── docs/                     # Documentación compartida
    ├── protocol.md           # Especificación del protocolo de datos
    └── architecture.md       # Diagrama de arquitectura
```

## 📡 Protocolo de Datos

**Buffer binario (little-endian):**
```
[uint32_t sample_idx (4B)][int32_t ch0 (4B)][int32_t ch1 (4B)]...[int32_t ch8 (4B)]
Total: 36 bytes por frame (8 canales + índice)
```

**Conversión a voltaje (lado DSP):**
```python
voltage = raw_value * LSB
# LSB = 2.235e-8 V
```

## 🔄 Flujo de Datos

1. **Arduino**: Lee ADS1299 → Empaqueta en buffer binario → Envía por Serial
2. **DSP**: Lee buffer Serial → Parsea datos → Convierte a voltaje → Procesa señal

## 🛠️ Desarrollo

### Arduino (PlatformIO)
```bash
cd arduino-firmware
platformio run --target upload
```

### DSP (Python)
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```
```bash
cd dsp-processor
pip install -r requirements.txt
python src/main.py
```

## 📊 Configuración

- **ADS1299**: 8 canales, 24-bit, RDATAC mode
- **Baudrate Serial**: 115200 bps
- **Frame Rate**: ~250 Hz (típico del ADS1299)
- **SPI DSP**: 1 MHz (futuro)
