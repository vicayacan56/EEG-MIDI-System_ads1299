# Consejos para Desarrollo Dual Arduino + DSP en VS Code

## 🎯 Estructura de Workspace Recomendada

### 1. **Workspace Multi-Carpeta (Recomendado)**

En VS Code: `File > Open Workspace from File...`

Crear archivo `EEG-MIDI-System.code-workspace`:

```json
{
  "folders": [
    {
      "path": "arduino-firmware",
      "name": "🔧 Arduino Firmware"
    },
    {
      "path": "dsp-processor",
      "name": "🐍 DSP Processor"
    },
    {
      "path": "docs",
      "name": "📚 Documentation"
    }
  ],
  "settings": {
    "files.exclude": {
      "**/.pio": true,
      "**/__pycache__": true,
      "**/venv": true
    },
    "search.exclude": {
      "**/node_modules": true,
      "**/.venv": true
    }
  }
}
```

**Ventajas:**
- ✅ Cambiar entre Arduino y Python sin reabrir VS Code
- ✅ Búsqueda en ambos proyectos simultáneamente
- ✅ Configuraciones independientes por carpeta

## 🛠️ Extensiones Esenciales

### Para Arduino (PlatformIO)

```
platformio.platformio-ide
ms-vscode.cpptools
```

### Para Python (DSP)

```
ms-python.python
ms-python.vscode-pylance
ms-toolsai.jupyter           # Para análisis interactivo
charliermarsh.ruff           # Linter rápido
ms-python.black-formatter
```

### Utilidades Compartidas

```
ms-vscode.remote-ssh         # Desarrollo remoto
eamodio.gitlens              # Control de versiones
ms-vscode.makefile-tools     # Build automation
```

## 📁 Estructura de Carpetas Optimizada

```
EEG-MIDI-System/
├── arduino-firmware/
│   ├── src/
│   │   └── main.cpp          ← AQUÍ: Interfaz ADS1299
│   ├── lib/
│   │   └── ADS1299Plus/       ← Driver del ADC
│   ├── platformio.ini
│   └── .vscode/
│       ├── settings.json      ← Configuración PlatformIO
│       └── extensions.json
│
├── dsp-processor/
│   ├── src/
│   │   ├── data_receiver.py   ← Lee del Arduino
│   │   ├── signal_processor.py ← Filtrado & análisis
│   │   └── main.py            ← Orquestador
│   ├── tests/
│   │   └── test_*.py
│   ├── notebooks/             ← Análisis Jupyter
│   │   └── exploratory.ipynb
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .vscode/
│       ├── settings.json      ← Python + Pylance
│       ├── launch.json        ← Configs de debug
│       └── extensions.json
│
├── docs/
│   ├── protocol.md            ← Especificación de datos
│   ├── architecture.md        ← Diagrama del sistema
│   └── development.md         ← Este archivo
│
└── EEG-MIDI-System.code-workspace ← Abrir esto en VS Code
```

## 🔧 Flujo de Desarrollo Recomendado

### 1. **Desarrollo Paralelo**

```
Ventana 1 (Arduino)          Ventana 2 (DSP)
├─ main.cpp                  ├─ main.py
├─ Compilar: Ctrl+Alt+B      ├─ Run: F5
├─ Serial Monitor: Ctrl+Alt+M├─ Debug: F5 con breakpoints
└─ Upload: Ctrl+Alt+U        └─ Tests: Ctrl+Shift+P > Run Tests
```

### 2. **Session de Debugging Sincronizado**

```
Arduino (PlatformIO)         DSP (Python)
      ↓                           ↓
  SERIAL MONITOR ←────────────→ DEBUG CONSOLE
  (Ver voltajes enviados)   (Ver datos parseados)
```

Terminal recomendada:
```powershell
# Terminal 1: Monitor Serial del Arduino
platformio device monitor --port COM3 --baud 115200

# Terminal 2: Script DSP con logging
python src/main.py --port COM3 --debug
```

## 🧪 Workflow de Testing

### Arduino: Validar envío

```cpp
// En main.cpp, agregar modo DEBUG:
#define DEBUG_BINARY_OUTPUT 1

if (DEBUG_BINARY_OUTPUT) {
  // Imprimir frame en hexadecimal para verificar formato
  for (uint8_t i = 0; i < FRAME_SIZE; i++) {
    if (buf[i] < 16) Serial.print("0");
    Serial.print(buf[i], HEX);
  }
  Serial.println();
}
```

### DSP: Validar recepción

```python
# En main.py, agregar:
import logging
logging.basicConfig(level=logging.DEBUG)

# Ver cada frame parseado
logger.debug(f"Frame: idx={sample_idx}, ch0={voltages[0]:.6f}V")
```

## 💾 Sincronización de Archivos

### .gitignore compartido

```
# Arduino
.pio/
.platformio/
*.elf
*.hex

# Python
__pycache__/
*.pyc
.pytest_cache/
venv/
*.egg-info/

# VS Code
.vscode/settings.local.json
.DS_Store
```

### Git Workflow

```bash
# Rama para features específicos
git checkout -b feature/dsp-filters
git commit -m "Add FIR filter implementation"

# Branching por tipo:
# feature/arduino-*     → Cambios en firmware
# feature/dsp-*         → Cambios en procesamiento
# docs/*                → Documentación
```

## 🚀 Optimizaciones para Desarrollo

### 1. **Tasks en VS Code** (`tasks.json`)

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Arduino: Build & Upload",
      "command": "platformio",
      "args": ["run", "-t", "upload"],
      "group": {"kind": "build"},
      "presentation": {"reveal": "always"}
    },
    {
      "label": "DSP: Run Demo",
      "command": "python",
      "args": ["dsp-processor/src/main.py", "--demo"],
      "group": {"kind": "build"}
    },
    {
      "label": "DSP: Run Tests",
      "command": "python",
      "args": ["-m", "pytest", "dsp-processor/tests/", "-v"],
      "group": {"kind": "test"}
    }
  ]
}
```

Uso: `Ctrl+Shift+B` → Seleccionar task

### 2. **Keyboard Shortcuts** (`keybindings.json`)

```json
[
  {
    "key": "ctrl+alt+a",
    "command": "workbench.action.tasks.runTask",
    "args": "Arduino: Build & Upload"
  },
  {
    "key": "ctrl+alt+p",
    "command": "workbench.action.tasks.runTask",
    "args": "DSP: Run Demo"
  }
]
```

### 3. **Live Share para Colaboración**

```bash
# Compartir workspace con compañero
Ctrl+Shift+P > Live Share: Start session
→ Comparten edición en tiempo real
```

## 📊 Herramientas para Análisis

### Jupyter Notebooks (Recomendado para DSP)

```python
# dsp-processor/notebooks/exploratory.ipynb

# Cargar datos parseados
import sys
sys.path.insert(0, '../src')
from data_receiver import DataReceiver

receiver = DataReceiver()
frames = receiver.read_multiple_frames(1000)

# Análisis interactivo
import matplotlib.pyplot as plt
signals = [f[1] for f in frames]  # Extraer voltajes
plt.plot(signals)
```

### Profiling (Rendimiento DSP)

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Código a perfilar
system.run(frames=1000)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative').print_stats(10)
```

## 🎯 Checklist de Setup Inicial

- [ ] Clonar/crear workspace: `EEG-MIDI-System/`
- [ ] Instalar PlatformIO IDE en VS Code
- [ ] Instalar Python Extension + Pylance
- [ ] Crear `.code-workspace` file
- [ ] `pip install -r dsp-processor/requirements.txt`
- [ ] Crear `python venv` en `dsp-processor/venv`
- [ ] Verificar conexión Arduino en Device Manager
- [ ] Probar Arduino upload: `platformio run -t upload`
- [ ] Probar DSP demo: `python dsp-processor/src/main.py --demo`
- [ ] Configurar Serial Monitor a 115200 bps
- [ ] ✅ Sistema listo para desarrollo

## 📞 Troubleshooting Común

| Problema | Solución |
|----------|----------|
| Python no encuentra módulos | `export PYTHONPATH=$PWD` en terminal |
| Arduino no se detecta | Revisar Device Manager, reinstalar CH340 drivers |
| Datos corruptos Serial | ✅ Verificar baudrate 115200 |
| Frame desincronizado | Agregar `sync_word` al inicio del frame |
| CPU alta en DSP | Profile con cProfile, optimizar filtros |

---

**¡Listo para comenzar!** 🚀
