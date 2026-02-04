# Protocolo de Comunicación: Arduino ↔ DSP Processor

## 📋 Especificación del Buffer Binario

El Arduino envía frames binarios con **codificación little-endian** a través de Serial (115200 bps).

### Estructura del Frame

```
Bytes 0-3:     uint32_t sample_idx         (índice de muestra, 4 bytes)
Bytes 4-7:     int32_t  channel_0          (canal 0, 4 bytes)
Bytes 8-11:    int32_t  channel_1          (canal 1, 4 bytes)
Bytes 12-15:   int32_t  channel_2          (canal 2, 4 bytes)
Bytes 16-19:   int32_t  channel_3          (canal 3, 4 bytes)
Bytes 20-23:   int32_t  channel_4          (canal 4, 4 bytes)
Bytes 24-27:   int32_t  channel_5          (canal 5, 4 bytes)
Bytes 28-31:   int32_t  channel_6          (canal 6, 4 bytes)
Bytes 32-35:   int32_t  channel_7          (canal 7, 4 bytes)
```

**Total: 36 bytes por frame**

### Formato Little-Endian (LSB-First)

```
Ejemplo: valor 0x12345678
Envío en bytes: 0x78, 0x56, 0x34, 0x12  ← LSB primero
```

### Codificación del Dato Raw

- **Origen**: ADS1299 (24-bit, signed)
- **Conversión**: Sign-extended a int32_t en Arduino
- **Rango**: ±8,388,608 (±2^23)
- **LSB Value**: 2.235 × 10⁻⁸ V/LSB

### Conversión a Voltaje (lado DSP)

```python
voltage = raw_int32 × 2.235e-8  [Voltios]
```

## 🔄 Secuencia de Transmisión

```
Arduino (ADS1299)          DSP Processor
      ↓                           ↓
   RDATAC Mode         (Serial listener @ 115200 bps)
      ↓                           ↓
  DRDY = LOW ────────Frame (36B)─────→ Read & Parse
      ↓                           ↓
  Read 24-bit × 8     Decode little-endian
      ↓                           ↓
  Sign-extend to 32    Convert to voltage
      ↓                           ↓
  Pack little-endian    Store en buffer
      ↓                           ↓
  Write(36 bytes)      Process DSP
```

## 📊 Parámetros del Sistema

| Parámetro | Valor | Unidad |
|-----------|-------|--------|
| Canales | 8 | - |
| Resolución | 24 | bits |
| Frecuencia Muestreo | ~250 | Hz |
| Frame Rate | ~250 | Hz |
| Baudrate | 115200 | bps |
| Bytes por frame | 36 | bytes |
| Throughput | ~9 | KB/s |

## 🧪 Test Frames (Sintético)

### Frame de Prueba: Todos los canales en 0

```
Hex: 00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
     00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00
     00 00 00 00
```

### Frame de Prueba: sample_idx=1, todos los canales=1000

```python
sample_idx = 1
channels = [1000] × 8

# Empaquetar:
frame = struct.pack('<I', 1)              # 01 00 00 00
frame += struct.pack('<8i', *[1000]*8)    # E8 03 00 00 × 8

# Resultado en Hex:
01 00 00 00  E8 03 00 00  E8 03 00 00  E8 03 00 00
E8 03 00 00  E8 03 00 00  E8 03 00 00  E8 03 00 00
E8 03 00 00
```

## 🔍 Debugging

### Verificar Sincronización

El campo `sample_idx` permite detectar pérdida de frames:

```python
expected_idx = previous_idx + 1
if received_idx != expected_idx:
    missed_frames = received_idx - expected_idx
    print(f"⚠ Pérdida de {missed_frames} frames")
```

### Validar Rango de Voltaje

Rango físico esperado: **±0.2 V** (típico para EEG)

```python
if abs(voltage) > 0.5:  # Umbral de alerta
    logger.warning(f"Valor fuera de rango: {voltage}V")
```

## 📝 Implementación en Python

```python
import struct

FRAME_SIZE = 36
NUM_CHANNELS = 8
LSB = 2.235e-8

def parse_frame(frame_bytes):
    """Parsea un frame binario del Arduino."""
    if len(frame_bytes) != FRAME_SIZE:
        raise ValueError(f"Frame incorrecto: {len(frame_bytes)} bytes")
    
    # Desempaquetar little-endian
    sample_idx = struct.unpack('<I', frame_bytes[0:4])[0]
    channels = struct.unpack('<8i', frame_bytes[4:36])
    
    # Convertir a voltaje
    voltages = [ch * LSB for ch in channels]
    
    return sample_idx, voltages
```

## 🚀 Casos de Uso Futuros

### SPI (Próxima Fase)

Para mayor velocidad (multi-canal, DSP avanzado):

```
SPI Settings: 1 MHz, MSBFIRST, Mode 0
Frame structure: Idéntica al protocolo Serial
CS pin: Definible (actualmente PIN_MCU_CS = 9)
```

### Handshake

Implementar ACK/NAK para verificar integridad de transmisión:

```
Arduino → DSP:  [36-byte frame]
DSP → Arduino:  0xAA (ACK) o 0x55 (NAK)
```
