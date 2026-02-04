#include <Arduino.h>

// Ejemplo de uso de la librería ADS1299Plus
// Mapea pines, inicializa el wrapper SPI seguro y el dispositivo ADS1299,
// luego entra en modo RDATAC y muestra frames por el monitor serie.

#include <SPI.h>
#include "ADS1299Plus.h"
#include "ADS1299_SafeSPI.h"

// Pines de ejemplo — ajústalos según tu placa y wiring.
// CS suele usarse en el pin 10 en muchos shields/placas Arduino.
// DRDY debe conectarse a un pin digital que pueda leerse (ej. 2).
static constexpr uint8_t PIN_CS    = 10;
static constexpr uint8_t PIN_SCLK  = SCK;
static constexpr uint8_t PIN_MOSI  = MOSI;
static constexpr uint8_t PIN_MISO  = MISO;
static constexpr uint8_t PIN_DRDY  = 2;
static constexpr uint8_t PIN_START = 3;
static constexpr uint8_t PIN_RESET = 4;
static constexpr uint8_t PIN_PWDN  = 5;

// Instancia del wrapper SPI y del driver ADS1299Plus
ADS1299_SafeSPI safeSpi(PIN_CS);
ADS1299Plus::Pins adsPins = { PIN_CS, PIN_SCLK, PIN_MOSI, PIN_MISO, PIN_DRDY, PIN_START, PIN_RESET, PIN_PWDN };
ADS1299Plus ads(safeSpi, adsPins);

// Configuración de salida hacia el microprocesador DSP
// Si `BINARY_OUTPUT` es true, el Arduino enviará frames binarios
// con el siguiente formato (little-endian):
// [uint32_t sample_idx][int32_t ch0][int32_t ch1]...[int32_t chN]
// Donde cada channel es un valor sign-extended de 24 bits en un int32_t.
static const bool BINARY_OUTPUT = true;

// Envío por SPI hacia el microprocesador DSP
// Define el pin CS que selecciona al microprocesador (ajústalo al socket "MCU_SPI3 / Sock SE5 SPI").
// Evita usar el mismo CS que el ADS1299 (PIN_CS).
static constexpr uint8_t PIN_MCU_CS = 9; // <--- cámbialo según tu wiring
static const bool USE_SPI_FOR_DSP = true; // true = enviar por SPI, false = usar Serial

// Contador de muestras enviado en cada frame
static uint32_t sample_idx = 0;

// Empaqueta y envía un frame por el puerto serie seleccionado.
// Usa orden little-endian: LSB primero.
static void sendSampleFrameBinary(Stream &serial, uint32_t idx, const int32_t ch[], uint8_t nchan) {
  // Tamaño: 4 bytes (idx) + 4*nchan bytes (canales)
  uint16_t len = 4 + 4 * nchan;
  // Buffer en stack — cuidado con MCU con poca RAM; nchan típicamente pequeño (4/8)
  uint8_t buf[4 + 4 * ADS1299Plus::NUM_CHANNELS];

  // Empaquetar sample_idx (little-endian)
  for (uint8_t i = 0; i < 4; ++i) buf[i] = (uint8_t)((idx >> (8 * i)) & 0xFF);

  // Empaquetar canales (cada int32_t en little-endian)
  for (uint8_t c = 0; c < nchan; ++c) {
    int32_t v = ch[c];
    uint16_t base = 4 + 4 * c;
    for (uint8_t b = 0; b < 4; ++b) {
      buf[base + b] = (uint8_t)((((uint32_t)v) >> (8 * b)) & 0xFF);
    }
  }

  serial.write(buf, len);
}

// Enviar frame binario por SPI (MCU como esclavo, Arduino como maestro)
// Envía LSB-first (little-endian) para cada campo.
static void sendSampleFrameSPI(uint8_t csPin, uint32_t idx, const int32_t ch[], uint8_t nchan) {
  // Configurar transacción SPI (1 MHz, modo 0)
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(csPin, LOW);

  // Enviar idx LSB-first
  for (uint8_t i = 0; i < 4; ++i) {
    SPI.transfer((uint8_t)((idx >> (8 * i)) & 0xFF));
  }

  // Enviar canales (int32_t) LSB-first
  for (uint8_t c = 0; c < nchan; ++c) {
    uint32_t v = (uint32_t)ch[c];
    for (uint8_t b = 0; b < 4; ++b) {
      SPI.transfer((uint8_t)((v >> (8 * b)) & 0xFF));
    }
  }

  digitalWrite(csPin, HIGH);
  SPI.endTransaction();
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }

  // Configuración de pines locales
  pinMode(PIN_DRDY, INPUT_PULLUP); // DRDY es activo bajo
  pinMode(PIN_START, OUTPUT);
  pinMode(PIN_RESET, OUTPUT);
  pinMode(PIN_PWDN, OUTPUT);
  digitalWrite(PIN_PWDN, HIGH); // dejar PWDN inactivo (HIGH) si el HW lo requiere

  // Inicializar SPI seguro y el ADS1299
  safeSpi.begin();
  if (!ads.begin()) {
    Serial.println("ERROR: ads.begin() falló");
    while (1) delay(1000);
  }

  if (!ads.configureDefaults()) {
    Serial.println("ERROR: configureDefaults() falló");
    while (1) delay(1000);
  }

  // Leer ID para verificar comunicación
  uint8_t devId = 0;
  if (ads.readDeviceID(devId)) {
    Serial.print("ADS1299 ID: 0x"); Serial.println(devId, HEX);
  } else {
    Serial.println("WARNING: no se leyó el ID del ADS1299");
  }

  // Entrar en modo de adquisición continua (RDATAC)
  ads.cmdRDATAC();
  Serial.println("Entrando en RDATAC. Esperando DRDY y mostrando frames...");
}

void loop() {
  // DRDY es activo bajo: cuando esté LOW, hay un frame listo.
  if (digitalRead(PIN_DRDY) == LOW) {
    uint32_t status;
    int32_t ch[ADS1299Plus::NUM_CHANNELS] = {0};

    if (ads.readFrameRDATAC(status, ch)) {
      // Imprime el estado y los canales convertidos a voltaje
      Serial.print("S:0x");
      Serial.print(status, HEX);

      // LSB según la imagen proporcionada
      const float LSB = 2.235e-8f;

      // `ads.readFrameRDATAC` ya devuelve canales sign-extended (int32_t)
      // gracias a `unpack24()` en `ADS1299Plus.h`.
      // Nota: `unpack24` hace sign-extension (MSB-first -> int32_t),
      // por eso `ch[]` ya contiene valores con signo listos para uso.
      
      if (BINARY_OUTPUT) {
        // Enviar frame binario al microprocesador DSP
        sendSampleFrameBinary(Serial, sample_idx, ch, ADS1299Plus::NUM_CHANNELS);
        sample_idx++;
      }
      
      // SIEMPRE mostrar valores en voltios por Serial para depuración
      // (independientemente de BINARY_OUTPUT)
      for (uint8_t i = 0; i < ADS1299Plus::NUM_CHANNELS; ++i) {
        float voltage = (float)ch[i] * LSB;
        Serial.print(" C"); Serial.print(i + 1); Serial.print(":");
        Serial.print(voltage, 2);
        if (i != (ADS1299Plus::NUM_CHANNELS - 1)) Serial.print(", ");
      }
      Serial.println();
    } else {
      Serial.println("Frame inválido o error de sincronía");
    }
  }
}