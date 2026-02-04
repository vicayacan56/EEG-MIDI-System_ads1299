// ADS1299_Registers.h
// Mapa de registros y campos del ADS1299 con helpers para configuración segura.
// Referencias: Datasheet ADS1299, sección 9.6 Register Maps + 9.6.1.x (User Register Description)

#pragma once
#include <stdint.h>


// =========================
//  SPI (9.5) — Comandos //opcodes que se envían por SPI para controlar el chip.
// =========================
enum : uint8_t {
  ADS_CMD_WAKEUP  = 0x02, // 9.5.3.2
  ADS_CMD_STANDBY = 0x04, // 9.5.3.3
  ADS_CMD_RESET   = 0x06, // 9.5.3.4
  ADS_CMD_START   = 0x08, // 9.5.3.5
  ADS_CMD_STOP    = 0x0A, // 9.5.3.6
  ADS_CMD_RDATAC  = 0x10, // 9.5.3.7
  ADS_CMD_SDATAC  = 0x11, // 9.5.3.8
  ADS_CMD_RDATA   = 0x12, // 9.5.3.9
  ADS_CMD_RREG    = 0x20, // 9.5.3.10 (OR con addr)
  ADS_CMD_WREG    = 0x40, // 9.5.3.11 (OR con addr)
  ADS_CMD_NOP     = 0x00
};

// =========================
//  Direcciones de registros (9.6) // Mapea nombres legibles a las direcciones 0x00..0x17. //Del 0x05 al 0x0C son los ocho CHnSET (config por canal).Los LOFF_STAT* son solo lectura; el resto son R/W.
// =========================
enum : uint8_t {
  ADS_REG_ID        = 0x00, // 9.6.1.1
  ADS_REG_CONFIG1   = 0x01, // 9.6.1.2
  ADS_REG_CONFIG2   = 0x02, // 9.6.1.3
  ADS_REG_CONFIG3   = 0x03, // 9.6.1.4
  ADS_REG_LOFF      = 0x04, // 9.6.1.5
  ADS_REG_CH1SET    = 0x05, // 9.6.1.6 (CH2..CH8 = +1..+7)
  ADS_REG_CH2SET    = 0x06,
  ADS_REG_CH3SET    = 0x07,
  ADS_REG_CH4SET    = 0x08,
  ADS_REG_CH5SET    = 0x09,
  ADS_REG_CH6SET    = 0x0A,
  ADS_REG_CH7SET    = 0x0B,
  ADS_REG_CH8SET    = 0x0C,
  ADS_REG_BIAS_SENSP= 0x0D, // 9.6.1.7
  ADS_REG_BIAS_SENSN= 0x0E, // 9.6.1.8
  ADS_REG_LOFF_SENSP= 0x0F, // 9.6.1.9
  ADS_REG_LOFF_SENSN= 0x10, // 9.6.1.10
  ADS_REG_LOFF_FLIP = 0x11, // 9.6.1.11
  ADS_REG_LOFF_STATP= 0x12, // 9.6.1.12 (R)
  ADS_REG_LOFF_STATN= 0x13, // 9.6.1.13 (R)
  ADS_REG_GPIO      = 0x14, // 9.6.1.14
  ADS_REG_MISC1     = 0x15, // 9.6.1.15
  ADS_REG_MISC2     = 0x16, // 9.6.1.16 (reservado)
  ADS_REG_CONFIG4   = 0x17  // 9.6.1.17
};

// =========================
//  ID (0x00) — 9.6.1.1  Estas máscaras extraen campos específicos del registro ID.
// =========================
// Bits [7:5] REV_ID, [4] = 1 (fix), [3:2] DEV_ID (ADS1299 = 11b), [1:0] NU_CH (00=4ch, 01=6ch, 10=8ch)
#define ADS_ID_REV_ID_MASK   0xE0 // revisión de silicio.
#define ADS_ID_DEV_ID_MASK   0x0C // identifica que es un ADS1299.
#define ADS_ID_NU_CH_MASK    0x03 // cuántos canales activos tiene.
#define ADS_ID_DEV_IS_1299(id) (((id)&ADS_ID_DEV_ID_MASK)==0x0C) // chequeo rápido para validación en firmware. el chip es un ADS1299 real y no otro dispositivo de la familia.

// =========================
//  CONFIG1 (0x01) — 9.6.1.2 // Construye el byte completo para CONFIG1. 
// EJEMPLO: 
// --> uint8_t config1 = ADS_CFG1_MAKE(false, false, ADS_DR_250);
// --> config1 = 0b10000110 = 0x86
// =========================
// [7]=1 (fix), [6]=DAISY_EN, [5]=CLK_EN, [2:0]=DR
#define ADS_CFG1_DAISY_EN    0x40 // Si está en 1, el chip está en modo daisy-chain (permite conectar varios ADS1299 en serie usando un solo bus SPI). //En nuestro diseño no lo usamos (sólo un ADS1299), así que lo dejaremos en 0.
#define ADS_CFG1_CLK_EN      0x20 // Si está en 1, la señal de reloj interno se copia al pin CLK (útil para sincronizar varios dispositivos). En nuestro caso desactivado.
// DR data rate:  Define los valores válidos de Data Rate (DR bits [2:0]).
enum : uint8_t {
  ADS_DR_16k   = 0b000,
  ADS_DR_8k    = 0b001,
  ADS_DR_4k    = 0b010,
  ADS_DR_2k    = 0b011,
  ADS_DR_1k    = 0b100,
  ADS_DR_500   = 0b101,
  ADS_DR_250   = 0b110, // recomendado
  // 111 reservado
};
#define ADS_CFG1_MAKE(daisy_en, clk_en, dr) (uint8_t)(0x80 | ((daisy_en)?ADS_CFG1_DAISY_EN:0) | ((clk_en)?ADS_CFG1_CLK_EN:0) | ((dr)&0x07))

// =========================
//  CONFIG2 (0x02) — 9.6.1.3 (Test tone) // Registro pensado para generar señales de prueba.
// EJEMPLO: 
// --> uint8_t config1 = ADS_CFG1_MAKE(false, false, ADS_DR_250);
// --> config1 = 0b10000110 = 0x86
// =========================
// ...xxx[4]=INT_CAL, [2]=CAL_AMP, [1:0]=CAL_FREQ
#define ADS_CFG2_INT_CAL     0x10 // Si está a 1, el chip inyecta internamente una señal de calibración en los canales seleccionados. //Si está a 0, el ADS1299 usa las entradas reales (electrodos).
#define ADS_CFG2_CAL_AMP_1X  0x00 // → amplitud normal (±(VREF / GAIN)).
#define ADS_CFG2_CAL_AMP_2X  0x04 // → amplitud doble.
enum : uint8_t { // CAL_FREQ Esto configura los bits [1:0] (CAL_FREQ)
  ADS_CALF_CLK_2_21 = 0b00, //señal senoidal a frecuencia fCLK / 2^21 (~1 Hz aprox con fCLK=2.048 MHz).
  ADS_CALF_CLK_2_20 = 0b01, //señal a fCLK / 2^20 (~2 Hz).
  ADS_CALF_RSVD     = 0b10, //Reservado.
  ADS_CALF_DC       = 0b11  //señal DC (nivel fijo).
};

#define ADS_CFG2_MAKE(intcal, amp2x, freq2b) (uint8_t)(0xC0 | ((intcal)?ADS_CFG2_INT_CAL:0) | ((amp2x)?ADS_CFG2_CAL_AMP_2X:ADS_CFG2_CAL_AMP_1X) | ((freq2b)&0x03)) //Construye el byte completo para CONFIG2. El operador AND (&) deja pasar solo los 2 bits menos significativos.

// =========================
//  CONFIG3 (0x03) — 9.6.1.4 (Referencia y BIAS)
// EJEMPLO: 
// uint8_t cfg3 = ADS_CFG3_MAKE(
  // true,   // useIntRef → buffer ref interno habilitado
  // false,  // biasMeas → no medir bias
  // true,   // biasRefInt → usar referencia interna
  // false,  // biasOn → no habilitar driver bias
  // false   // biasLoffSens → lead-off no por bias
// );
// =========================
// [7]=PD_REFBUF, [4]=BIAS_MEAS, [3]=BIASREF_INT, [2]=PD_BIAS, [1]=BIAS_LOFF_SENS, [0]=BIAS_STAT (R)
#define ADS_CFG3_PD_REFBUF     0x80 // Controla el buffer de referencia interna (4.5 V).
#define ADS_CFG3_BIAS_MEAS     0x10 //Permite medir BIASIN respecto a BIASREF usando el MUX de canal. solo habilita la ruta de medida. Útil para debug.
#define ADS_CFG3_BIASREF_INT   0x08 //Selecciona la referencia de BIAS: interna (≈ (AVDD+AVSS)/2) o externa (pin BIASREF).
#define ADS_CFG3_PD_BIAS       0x04 // Controla el amplificador/driver BIAS (salida en BIASOUT).
#define ADS_CFG3_BIAS_LOFF_SENS 0x02 // Habilita que el sensado de lead-off se haga a través del nodo BIAS (modo alternativo).
// helper
#define ADS_CFG3_MAKE(useIntRef, biasMeas, biasRefInt, biasOn, biasLoffSens) \
  (uint8_t)((useIntRef?ADS_CFG3_PD_REFBUF:0) | (biasMeas?ADS_CFG3_BIAS_MEAS:0) | (biasRefInt?ADS_CFG3_BIASREF_INT:0) | (biasOn?ADS_CFG3_PD_BIAS:0) | (biasLoffSens?ADS_CFG3_BIAS_LOFF_SENS:0))




// =========================
//  LOFF (0x04) — 9.6.1.5 (Lead-Off ctrl) // controla la detección de electrodos sueltos
// =========================
// [7:5]=COMP_TH, [3:2]=ILEAD_OFF, [1:0]=FLEAD_OFF
// Threshold comparador (ejemplos comunes; consulta tabla exacta de %) umbral del comparador
#define ADS_LOFF_COMPTH_95   (0b000<<5)
#define ADS_LOFF_COMPTH_90   (0b001<<5)
#define ADS_LOFF_COMPTH_85   (0b010<<5)
#define ADS_LOFF_COMPTH_80   (0b011<<5)
#define ADS_LOFF_COMPTH_75   (0b100<<5)
// Corriente lead-off
#define ADS_LOFF_I_6nA       (0b00<<2)
#define ADS_LOFF_I_24nA      (0b01<<2)
#define ADS_LOFF_I_6uA       (0b10<<2)
#define ADS_LOFF_I_24uA      (0b11<<2)
// Frecuencia AC lead-off
#define ADS_LOFF_F_DC        (0b00)
#define ADS_LOFF_F_7_8HZ     (0b01)
#define ADS_LOFF_F_31_2HZ    (0b10)
#define ADS_LOFF_F_FDR_4     (0b11) // fDR/4
#define ADS_LOFF_MAKE(comp, ilead, flead) (uint8_t)((comp) | (ilead) | ((flead)&0x03))

// =========================
//  CHnSET (0x05..0x0C) — 9.6.1.6 (Canales)
// =========================
// [7]=PDn, [6:4]=GAIN, [3]=SRB2, [2:0]=MUX
#define ADS_CH_PD            0x80
// GAIN
enum : uint8_t { ADS_GAIN_1=0b000, ADS_GAIN_2=0b001, ADS_GAIN_4=0b010, ADS_GAIN_6=0b011, ADS_GAIN_8=0b100, ADS_GAIN_12=0b101, ADS_GAIN_24=0b110 };
// MUX
enum : uint8_t {
  ADS_MUX_NORMAL  = 0b000, // entrada diferencial normal (full diff)
  ADS_MUX_SHORT   = 0b001, // entradas cortocircuitadas (ruido interno)
  ADS_MUX_BIAS_MEAS=0b010, // mide BIASIN vs BIASREF
  ADS_MUX_MVDD    = 0b011, // medición fuentes (ver notas canales)
  ADS_MUX_TEMP    = 0b100, // sensor temperatura
  ADS_MUX_TESTSIG = 0b101, // test interno (CONFIG2)
  ADS_MUX_BIASP   = 0b110, // BIAS_DR en P
  ADS_MUX_BIASN   = 0b111  // BIAS_DR en N
};
#define ADS_CH_SRB2          0x08
#define ADS_CH_MAKE(on, gain3b, mux3b, srb2) (uint8_t)(((on)?0:ADS_CH_PD) | ((gain3b&0x07)<<4) | ((srb2)?ADS_CH_SRB2:0) | (mux3b&0x07))

// =========================
//  BIAS_SENSP / BIAS_SENSN (0x0D/0x0E) — 9.6.1.7/8
// =========================
// Bits por canal: 1=incluye esa polaridad en la derivación de BIAS
// (en nuestro diseño: se dejan a 0x00 porque no usamos bias drive)
#define ADS_MASK_CH1 0x01
#define ADS_MASK_CH2 0x02
#define ADS_MASK_CH3 0x04
#define ADS_MASK_CH4 0x08
#define ADS_MASK_CH5 0x10 
#define ADS_MASK_CH6 0x20
#define ADS_MASK_CH7 0x40
#define ADS_MASK_CH8 0x80

static inline uint8_t ADS_ClipMaskToChannels(uint8_t mask, uint8_t nchan) {
  static const uint8_t lut[9] = {0x00,0x01,0x03,0x07,0x0F,0x1F,0x3F,0x7F,0xFF};  // ADS_ClipMaskToChannels(mask, 4) asegura que solo queden activos los bits 0..3 (CH1..CH4).
  if (nchan>8) nchan = 8;
  return (uint8_t)(mask & lut[nchan]);
}

// =========================
//  LOFF_SENSP / LOFF_SENSN (0x0F/0x10) — 9.6.1.9/10 // Habilita la detección de desconexión (lead-off) en la entrada positiv y/o negativa de cada canal.
// =========================
// Bits por canal: 1=activa detección lead-off en esa polaridad
// (habilitar según canales activos)
#define ADS_LOFF_SENS_MASK(chMask) ((uint8_t)(chMask))

// =========================
//  LOFF_FLIP (0x11) — 9.6.1.11
// =========================
// Bits por canal: 1=invierte dirección corriente lead-off (usar en barridos DC)
#define ADS_LOFF_FLIP_MASK(chMask) ((uint8_t)(chMask))

// =========================
// —  LOFF_STATP / LOFF_STATN (0x12/0x13) — 9.6.1.12/13 (R)
// =========================
// Se leen para conocer estado de contacto (P/N) por canal (1=off según umbral COMP_TH).
inline bool ADS_IsLeadOffP(uint8_t statP, uint8_t ch) {
  return (statP >> (ch-1)) & 0x01; // true si OFF
}

inline bool ADS_IsLeadOffN(uint8_t statN, uint8_t ch) {
  return (statN >> (ch-1)) & 0x01; // true si OFF
}
// =========================
//  GPIO (0x14) — 9.6.1.14
// =========================
// [7:4]=GPIOD (data), [3:0]=GPIOC (dir; 1=input, 0=output)
#define ADS_GPIO_DIR_IN_ALL   0x0F
#define ADS_GPIO_DIR_OUT_ALL  0x00
#define ADS_GPIO_MAKE(data4, dir4) (uint8_t)(((data4&0x0F)<<4) | (dir4&0x0F))

// =========================
//  MISC1 (0x15) — 9.6.1.15
// =========================
// [5]=SRB1: 1=ruta SRB1 a todas las entradas inversoras (INxN)
#define ADS_MISC1_SRB1_EN     0x20
// Backwards-compatible alias: some source files use `ADS_MISC1_SRB1` (without `_EN`).
#define ADS_MISC1_SRB1        ADS_MISC1_SRB1_EN

// =========================
//  MISC2 (0x16) — 9.6.1.16 (Reservado)
// =========================

// =========================
//  CONFIG4 (0x17) — 9.6.1.17
// =========================
// [3]=SINGLE_SHOT (1=single-shot, 0=continuo), [1]=PD_LOFF_COMP (0=ON, 1=PD?)*
// Nota: algunos diagramas invierten semántica; verifica tu revisión de datasheet.
#define ADS_CFG4_SINGLE_SHOT   0x08
#define ADS_CFG4_PD_LOFF_COMP  0x02
#define ADS_CFG4_CONT_CONV     0x00 // SINGLE_SHOT=0

// =========================
//  STATUS (24 bits al inicio de cada frame RDATAC) — 9.4.4.2
// =========================
// STATUS[23:20] = 1100b
// STATUS[19:12] = LOFF_STATP (ch8..ch1)
// STATUS[11:4]  = LOFF_STATN (ch8..ch1)
// STATUS[3:0]   = GPIO[4:1]
#define ADS_STATUS_SYNC_MASK   0xF00000u
#define ADS_STATUS_SYNC_VAL    0xC00000u
#define ADS_STATUS_LOFFP(s)    (uint8_t)(((s)>>12)&0xFF)
#define ADS_STATUS_LOFFN(s)    (uint8_t)(((s)>>4 )&0xFF)
#define ADS_STATUS_GPIO4_1(s)  (uint8_t)((s)&0x0F)

// =========================
//  Defaults recomendados (tu configuración)
// =========================

// CONFIG1: DR=250SPS, sin daisy, sin clock out
static constexpr uint8_t ADS_CFG1_250SPS =
  ADS_CFG1_MAKE(false/*daisy*/, false/*clk_out*/, ADS_DR_250);

// CONFIG2: test tones OFF (int_cal=0), (amp=1x), (freq=clk/2^21)
static constexpr uint8_t ADS_CFG2_TEST_OFF =
  ADS_CFG2_MAKE(false, false, ADS_CALF_CLK_2_21);

// CONFIG3: referencia interna ON, bias OFF, sin medir bias, sin bias_loff_sens
static constexpr uint8_t ADS_CFG3_INTREF_NO_BIAS =
  ADS_CFG3_MAKE(true/*refbuf*/, false/*bias_meas*/, true/*biasref_int*/, false/*bias_on*/, false/*bias_loff_sens*/);

// LOFF: DC+AC — I=24nA, F=31.2Hz, COMP_TH≈80–85% (ajusta según pruebas)
static constexpr uint8_t ADS_LOFF_DCAC_24nA_31Hz_80pct =
  ADS_LOFF_MAKE(ADS_LOFF_COMPTH_80, ADS_LOFF_I_24nA, ADS_LOFF_F_31_2HZ);

// CHnSET típicos: canal ON, GAIN=24, MUX=normal (full diff), SRB2 OFF
inline uint8_t ADS_CH_DEFAULT_GAIN24() {
  return ADS_CH_MAKE(true/*on*/, ADS_GAIN_24, ADS_MUX_NORMAL, false/*srb2*/);
}

// GPIO: todas entradas (si no se usan). Data=0.
static constexpr uint8_t ADS_GPIO_ALL_INPUTS =
  ADS_GPIO_MAKE(0x0, ADS_GPIO_DIR_IN_ALL);

// CONFIG4: continuo y comparadores ON
static constexpr uint8_t ADS_CFG4_CONT_LOFF_ON =
  (ADS_CFG4_CONT_CONV /*0*/) /* PD_LOFF_COMP=0 → comparadores habilitados */;
