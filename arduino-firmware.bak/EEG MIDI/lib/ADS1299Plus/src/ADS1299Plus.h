// ADS1299Plus.h
// Clase de alto nivel para configurar y adquirir datos del ADS1299
// Basado en el datasheet (secciones 9.4, 9.5 y 9.6) y en tus requisitos:
// - Entradas fully differential
// - Ganancia = 24
// - Referencia interna
// - Data rate = 250 SPS (Fmod/4096)
// - Reloj interno (CLK_OUT deshabilitado)
// - Bias drive deshabilitado
// - Lead-Off combinado DC+AC (comparadores ON)
// - GPIO como entrada por defecto
//
// Esta cabecera solo declara la API y utilidades inline. La implementación
// de SPI y temporizaciones vivirá en ADS1299_SafeSPI.* y ADS1299Plus.cpp

#pragma once
#include <Arduino.h>
#include "ADS1299_Registers.h"

// Forward-declaration del wrapper SPI seguro que crearemos a continuación.
class ADS1299_SafeSPI;

class ADS1299Plus {
public:
  // ----- Constantes del dispositivo -----
  static constexpr uint8_t  NUM_CHANNELS = 4;
  static constexpr uint16_t BYTES_PER_FRAME_8CH = 3 /*status*/ + 3*NUM_CHANNELS;

  // ----- Estructura de pines para claridad -----
  struct Pins {
    uint8_t cs;     // CS  (activo a nivel bajo)
    uint8_t sclk;   // SCLK
    uint8_t mosi;   // DIN  (MCU->ADS)
    uint8_t miso;   // DOUT (ADS->MCU)
    uint8_t drdy;   // DRDY (ADS->MCU) activo bajo
    uint8_t start;  // START (MCU->ADS)
    uint8_t reset;  // RESET (MCU->ADS)
    uint8_t pwdn;   // PWDN  (MCU->ADS), dejar alto si no se usa
  };

  // ----- Config por defecto (lo que acordamos) -----
  // 9.6.1.2  CONFIG1: DR=250SPS, sin daisy, sin clock out
  static constexpr uint8_t kCFG1_Default   = ADS_CFG1_250SPS;

  // 9.6.1.3  CONFIG2: test off
  static constexpr uint8_t kCFG2_Default   = ADS_CFG2_TEST_OFF;

  // 9.6.1.4  CONFIG3: ref interna ON, bias OFF, no medir bias
  static constexpr uint8_t kCFG3_Default   = ADS_CFG3_INTREF_NO_BIAS;

  // 9.6.1.5  LOFF: DC+AC (31.2 Hz), I=24 nA, umbral ~80 %
  static constexpr uint8_t kLOFF_Default   = ADS_LOFF_DCAC_24nA_31Hz_80pct;

  // 9.6.1.6  CHnSET por defecto: ON, GAIN=24, MUX=normal diff, SRB2=OFF
  static inline uint8_t kCH_Default() { return ADS_CH_DEFAULT_GAIN24(); }

  // 9.6.1.14 GPIO: todos como entrada
  static constexpr uint8_t kGPIO_Default   = ADS_GPIO_ALL_INPUTS;

  // 9.6.1.17 CONFIG4: continuo, comparadores de lead-off habilitados
  static constexpr uint8_t kCFG4_Default   = ADS_CFG4_CONT_LOFF_ON;

public:
  // ----- Construcción -----
  ADS1299Plus(ADS1299_SafeSPI& spi, const Pins& pins);

  // ----- Ciclo de vida -----
  // 11.1 Power-Up Sequencing + 9.4/9.5 (resets, delays, etc.)
  // Configura pines, aplica power-up seguro, emite RESET y deja el chip listo.
  bool begin();

  // Lleva el dispositivo a un estado conocido (STOP + SDATAC),
  // programa todos los registros con los valores por defecto de arriba
  // y verifica el ID (9.6.1.1). Llama a esto tras begin().
  bool configureDefaults();

  // Para liberar pines/ISR si procede
  void end();

  // ----- Comandos SPI (9.5.3.x) -----
  void cmdWakeup();     // 0x02
  void cmdStandby();    // 0x04
  void cmdReset();      // 0x06
  void cmdStart();      // 0x08
  void cmdStop();       // 0x0A
  void cmdRDATAC();     // 0x10
  void cmdSDATAC();     // 0x11
  void cmdRDATA();      // 0x12

  // ----- Acceso a registros (9.5.3.10/11) -----
  // r/w de 1 registro
  bool writeReg(uint8_t addr, uint8_t value);
  bool readReg (uint8_t addr, uint8_t& value);

  // r/w de ráfaga (n >= 1). n es número de registros consecutivos.
  bool writeRegs(uint8_t startAddr, const uint8_t* data, size_t n);
  bool readRegs (uint8_t startAddr,       uint8_t* data, size_t n);

  // Helpers de alto nivel para mapear 9.6:
  bool setDataRate(uint8_t dr3b);                      // CONFIG1.DR[2:0]
  bool setClockOut(bool enable);                       // CONFIG1.CLK_EN
  bool setDaisyEnable(bool enable);                    // CONFIG1.DAISY_EN

  bool setChannel(uint8_t ch, uint8_t chsetByte);      // CHnSET n=[1..8]
  bool powerDownChannel(uint8_t ch, bool pd);
  bool setChannelGain(uint8_t ch, uint8_t gain3b);
  bool setChannelMux (uint8_t ch, uint8_t mux3b);
  bool setSRB2(uint8_t ch, bool en);

  bool enableSRB1(bool en);                            // MISC1.SRB1

  // BIAS/Referencia (CONFIG3):
  bool useInternalRef(bool enBuf);                     // PD_REFBUF (buf ON=1)
  bool useBiasInternalRef(bool enInt);                 // BIASREF_INT
  bool enableBiasBuffer(bool en);                      // PD_BIAS (en=1)
  bool routeBiasSense(bool en);                        // BIAS_LOFF_SENS
  bool enableBiasMeasure(bool en);                     // BIAS_MEAS

  // Lead-Off (LOFF + LOFF_SENSP/N + LOFF_FLIP + CONFIG4):
  bool configureLeadOff(uint8_t loffByte);             // 9.6.1.5
  bool enableLeadOffSenseP(uint8_t chMask);            // 9.6.1.9
  bool enableLeadOffSenseN(uint8_t chMask);            // 9.6.1.10
  bool setLeadOffFlip(uint8_t chMask);                 // 9.6.1.11
  bool setSingleShot(bool singleShot);                 // CONFIG4.SINGLE_SHOT
  bool enableLoffComparators(bool en);                 // CONFIG4.PD_LOFF_COMP (en=true => bit=0)

  // BIAS derivation (no usado por defecto, pero expuesto):
  bool setBiasDeriveP(uint8_t chMask);                 // BIAS_SENSP
  bool setBiasDeriveN(uint8_t chMask);                 // BIAS_SENSN

  // ----- Adquisición -----
  // Lee un frame completo en RDATAC: 24b STATUS + 4×24b canales.
  // Devuelve false si el patrón de sync (1100) no coincide.
  bool readFrameRDATAC(uint32_t& status24, int32_t chOut[NUM_CHANNELS]);

  // Lee “on demand” tras RDATA (igual formato que RDATAC).
  bool readDataOnDemand(uint32_t& status24, int32_t chOut[NUM_CHANNELS]);

  // Decodificadores de STATUS (9.4.4.2)
  static inline bool statusHasSync(uint32_t s) {
    return (s & ADS_STATUS_SYNC_MASK) == ADS_STATUS_SYNC_VAL;
  }
  static inline uint8_t statusLoffP(uint32_t s) { return ADS_STATUS_LOFFP(s); }
  static inline uint8_t statusLoffN(uint32_t s) { return ADS_STATUS_LOFFN(s); }
  static inline uint8_t statusGPIO (uint32_t s) { return ADS_STATUS_GPIO4_1(s); }

  // ----- Utilidades -----
  // Convierte 3 bytes MSB-first en entero con signo (24 bits -> 32 bits)
  static inline int32_t unpack24(const uint8_t b[3]) {
    uint32_t u = ((uint32_t)b[0] << 16) | ((uint32_t)b[1] << 8) | b[2];
    // sign-extend a 32 bits si MSB de 24b está a 1
    if (u & 0x00800000UL) u |= 0xFF000000UL;
    return (int32_t)u;
  }

  // Devuelve el ID crudo (registro 0x00) para logging/verificación
  bool readDeviceID(uint8_t& id);

  // Acceso a pines (por si el usuario quiere controlar START/RESET manual)
  void pinStartHigh();
  void pinStartLow ();
  void pinResetPulse();     // ≥2 tCLK (según 9.4.2/11.1 – lo implementamos en .cpp)
  void pinPowerDown(bool activeLow);

private:
  // Helpers internos
  bool writeOne_(uint8_t addr, uint8_t val);
  bool readOne_ (uint8_t addr, uint8_t& val);

  bool writeBurst_(uint8_t startAddr, const uint8_t* data, size_t n);
  bool readBurst_ (uint8_t startAddr,       uint8_t* data, size_t n);

  // Comprobación y normalización de índices [1..8]
  static inline bool validCh_(uint8_t ch) { return ch>=1 && ch<=NUM_CHANNELS; }
  static inline uint8_t chRegAddr_(uint8_t ch) { return ADS_REG_CH1SET + (ch-1); }

  // Construcción de CHnSET a partir de sus campos (9.6.1.6)
  static inline uint8_t makeCH_(bool on, uint8_t gain3b, uint8_t mux3b, bool srb2) {
    return ADS_CH_MAKE(on, gain3b, mux3b, srb2);
  }

private:
  ADS1299_SafeSPI& spi_;  // transporte SPI con guardas de timing (tSDECODE, etc.)
  Pins pins_;
  bool rdatacActive_ = false;
  // Número de canales detectado (4/6/8) — inicializa al máximo soportado
  uint8_t num_channels_ = NUM_CHANNELS;
};
