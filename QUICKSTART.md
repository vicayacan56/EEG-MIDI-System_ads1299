# Quick Start Guide - EEG MIDI System

## ⚡ Inicio Rápido (5 minutos)

### 1️⃣ Abrir Workspace

```powershell
cd C:\Users\PC\Documents\EEG-MIDI-System
code EEG-MIDI-System.code-workspace
```

### 2️⃣ Instalar Dependencias Python

```powershell
# Terminal en VS Code (Ctrl+`)
Ctrl+Shift+P > Run Task > 🐍 DSP: Install Dependencies
```

O manualmente:
```bash
pip install -r dsp-processor/requirements.txt
```

### 3️⃣ Verificar Conexión Arduino

```bash
Ctrl+Shift+P > Run Task > 🔧 Arduino: Serial Monitor
```

Debería ver datos en hexadecimal del ADS1299.

### 4️⃣ Ejecutar DSP Demo

```bash
Ctrl+Shift+P > Run Task > 🐍 DSP: Run Demo (Synthetic Data)
```

Verá análisis en tiempo real de datos sintéticos.

### 5️⃣ Ejecutar DSP con Arduino Real

```bash
Ctrl+Shift+P > Run Task > 🐍 DSP: Run Real (COM3)
```

El DSP comenzará a leer del Arduino.

---

## 📋 Cambios a tu Proyecto Arduino Existente

El código Arduino en tu proyecto actual YA está optimizado. Solo necesitas:

1. Verificar que `BINARY_OUTPUT = true` en `main.cpp`
2. Confirmar que baudrate es `115200`
3. Adjuntar/copiar este nuevo proyecto DSP en paralelo

---

## 🗂️ Estructura Final

```
C:\Users\PC\Documents\
├── PlatformIO\Projects\EEG MIDI\        ← Tu proyecto original (sin cambios)
│   ├── src\main.cpp                    ✅ Ya actualizamos esto
│   └── ...
│
└── EEG-MIDI-System\                     ← NUEVO workspace dual
    ├── arduino-firmware\                (Link/copia de tu proyecto)
    ├── dsp-processor\                   (Sistema DSP Python)
    ├── docs\
    └── EEG-MIDI-System.code-workspace  ← Abrir ESTO en VS Code
```

---

## 🎯 Siguientes Pasos

### Corto Plazo (Esta semana)
1. ✅ Validar que Arduino envía datos correctamente
2. ✅ Verificar que DSP recibe y parsea frames
3. ✅ Confirmar conversión a voltaje
4. ✅ Implementar filtros básicos

### Mediano Plazo (Este mes)
1. Análisis espectral avanzado (FFT, Welch)
2. Detección de bandas EEG (alpha, beta, gamma)
3. Interfaz gráfica de monitoreo en tiempo real
4. Exportar datos a CSV/HDF5

### Largo Plazo (Próximos meses)
1. Implementar comunicación SPI Arduino ↔ DSP
2. Generación de MIDI en tiempo real
3. Detección de eventos (seizure, artifacts)
4. Machine Learning (clasificación de estados)

---

## 🐛 Troubleshooting

| Error | Causa | Solución |
|-------|-------|----------|
| "No module named 'serial'" | PySerial no instalado | `pip install pyserial` |
| "COM3 not found" | Arduino no conectado | Verificar Device Manager |
| "Frame incompleto" | Baudrate incorrecto | Cambiar a 115200 en settings |
| "Valores fuera de rango" | Error en conversión | Ver `protocol.md` |

---

## 📞 Comandos Útiles

```bash
# Listar puertos COM disponibles
python -m serial.tools.list_ports

# Test rápido de lectura
python dsp-processor/src/data_receiver.py

# Ejecutar tests
python -m pytest dsp-processor/tests/ -v

# Profile de rendimiento
python -m cProfile -s cumulative dsp-processor/src/main.py --demo
```

---

**¿Listo?** → Presiona F5 o ejecuta una task. 🚀
