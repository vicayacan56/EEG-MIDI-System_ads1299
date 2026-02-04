// ADS1299Plus.cpp

#include "ADS1299Plus.h"
#include "ADS1299_SafeSPI.h"
#include "ADS1299_Registers.h"

// Utilidades internas de tiempo
static inline void ads_wait_us(uint32_t us) { delayMicroseconds(us); }
static inline void ads_wait_ms(uint32_t ms) { delay(ms); }
static inline void ads_wait_decode() { delayMicroseconds(3); }

// ---- Constructor ----
ADS1299Plus::ADS1299Plus(ADS1299_SafeSPI &spi, const Pins &pins)
    : spi_(spi), pins_(pins) {}

// ---- Control de pines auxiliares ----
void ADS1299Plus::pinStartHigh() { digitalWrite(pins_.start, HIGH); }
void ADS1299Plus::pinStartLow() { digitalWrite(pins_.start, LOW); }

void ADS1299Plus::pinResetPulse()
{
  digitalWrite(pins_.reset, LOW);
  ads_wait_us(10);
  digitalWrite(pins_.reset, HIGH);
  ads_wait_us(20);
}

void ADS1299Plus::pinPowerDown(bool activeLow)
{
  digitalWrite(pins_.pwdn, activeLow ? LOW : HIGH);
}

// ---- Secuencia de arranque (11.1) ----
bool ADS1299Plus::begin()
{
  // 1) Configurar pines
  pinMode(pins_.cs, OUTPUT);
  digitalWrite(pins_.cs, HIGH);
  pinMode(pins_.sclk, OUTPUT);
  pinMode(pins_.mosi, OUTPUT);
  pinMode(pins_.miso, INPUT);
  pinMode(pins_.drdy, INPUT);
  pinMode(pins_.start, OUTPUT);
  digitalWrite(pins_.start, LOW);
  pinMode(pins_.reset, OUTPUT);
  digitalWrite(pins_.reset, HIGH);

  // 2) Esperar a que las fuentes se estabilicen
  ads_wait_ms(5);

  // 3) Inicializar SPI seguro
  spi_.begin();

  // 4) Reset digital
  cmdReset();

  // 5) Detener conversión
  cmdStop();
  cmdSDATAC();

  // 6) Verificar ID
  uint8_t id = 0;
  if (!readReg(ADS_REG_ID, id))
    return false;
  if (!ADS_ID_DEV_IS_1299(id))
    return false;

  // Ajustar número de canales
  switch (id & ADS_ID_NU_CH_MASK)
  {
  case 0b00:
    num_channels_ = 4;
    break;
  case 0b01:
    num_channels_ = 6;
    break;
  case 0b10:
    num_channels_ = 8;
    break;
  default:
    num_channels_ = 4;
    break;
  }

  return true;
}

// ---- Configuración por defecto ----
bool ADS1299Plus::configureDefaults()
{
  cmdStop();
  cmdSDATAC();

  if (!writeReg(ADS_REG_CONFIG1, kCFG1_Default))
    return false;
  if (!writeReg(ADS_REG_CONFIG2, kCFG2_Default))
    return false;
  if (!writeReg(ADS_REG_CONFIG3, kCFG3_Default))
    return false;
  if (!writeReg(ADS_REG_LOFF, kLOFF_Default))
    return false;

  // Configurar canales activos
  for (uint8_t ch = 1; ch <= num_channels_; ++ch)
  {
    if (!setChannel(ch, kCH_Default()))
      return false;
  }

  // Apagar canales inactivos
  for (uint8_t ch = num_channels_ + 1; ch <= 8; ++ch)
  {
    if (!powerDownChannel(ch, true))
      return false;
  }

  // BIAS derivation: desactivar
  if (!writeReg(ADS_REG_BIAS_SENSP, 0x00))
    return false;
  if (!writeReg(ADS_REG_BIAS_SENSN, 0x00))
    return false;

  // Lead-off sense en canales activos
  uint8_t activeMask = 0xFF;
  if (num_channels_ < 8)
  {
    activeMask = (1 << num_channels_) - 1;
  }
  if (!enableLeadOffSenseP(activeMask))
    return false;
  if (!enableLeadOffSenseN(activeMask))
    return false;

  if (!writeReg(ADS_REG_LOFF_FLIP, 0x00))
    return false;
  if (!writeReg(ADS_REG_GPIO, kGPIO_Default))
    return false;
  if (!writeReg(ADS_REG_MISC1, 0x00))
    return false;
  if (!writeReg(ADS_REG_CONFIG4, kCFG4_Default))
    return false;

  return true;
}

void ADS1299Plus::end()
{
  cmdStop();
  cmdSDATAC();
  spi_.end();
}

// ---- Comandos SPI ----
void ADS1299Plus::cmdWakeup()
{
  spi_.select();
  spi_.xfer(ADS_CMD_WAKEUP);
  spi_.deselect();
  ads_wait_decode();
}
void ADS1299Plus::cmdStandby()
{
  spi_.select();
  spi_.xfer(ADS_CMD_STANDBY);
  spi_.deselect();
  ads_wait_decode();
}

void ADS1299Plus::cmdReset()
{
  spi_.select();
  spi_.xfer(ADS_CMD_RESET);
  spi_.deselect();
  ads_wait_us(20);
}

void ADS1299Plus::cmdStart()
{
  spi_.select();
  spi_.xfer(ADS_CMD_START);
  spi_.deselect();
  ads_wait_decode();
}
void ADS1299Plus::cmdStop()
{
  spi_.select();
  spi_.xfer(ADS_CMD_STOP);
  spi_.deselect();
  ads_wait_decode();
}
void ADS1299Plus::cmdRDATAC()
{
  spi_.select();
  spi_.xfer(ADS_CMD_RDATAC);
  spi_.deselect();
  rdatacActive_ = true;
  ads_wait_decode();
}
void ADS1299Plus::cmdSDATAC()
{
  spi_.select();
  spi_.xfer(ADS_CMD_SDATAC);
  spi_.deselect();
  rdatacActive_ = false;
  ads_wait_decode();
}
void ADS1299Plus::cmdRDATA()
{
  spi_.select();
  spi_.xfer(ADS_CMD_RDATA);
  spi_.deselect();
}

// ---- Acceso a registros ----n
bool ADS1299Plus::writeOne_(uint8_t addr, uint8_t val)
{
  spi_.select();
  spi_.xfer(ADS_CMD_WREG | addr);
  spi_.xfer(0x00); // write 1 reg
  spi_.xfer(val);
  spi_.deselect();
  ads_wait_decode();
  return true;
}

bool ADS1299Plus::readOne_(uint8_t addr, uint8_t &val)
{
  spi_.select();
  spi_.xfer(ADS_CMD_RREG | addr);
  spi_.xfer(0x00); // read 1 reg
  val = spi_.xfer(0x00);
  spi_.deselect();
  ads_wait_decode();
  return true;
}

bool ADS1299Plus::writeBurst_(uint8_t startAddr, const uint8_t *data, size_t n)
{
  spi_.select();
  spi_.xfer(ADS_CMD_WREG | startAddr);
  spi_.xfer(n - 1);
  for (size_t i = 0; i < n; ++i)
  {
    spi_.xfer(data[i]);
  }
  spi_.deselect();
  ads_wait_decode();
  return true;
}

bool ADS1299Plus::readBurst_(uint8_t startAddr, uint8_t *data, size_t n)
{
  spi_.select();
  spi_.xfer(ADS_CMD_RREG | startAddr);
  spi_.xfer(n - 1);
  for (size_t i = 0; i < n; ++i)
  {
    data[i] = spi_.xfer(0x00);
  }
  spi_.deselect();
  ads_wait_decode();
  return true;
}

bool ADS1299Plus::writeReg(uint8_t addr, uint8_t value) { return writeOne_(addr, value); }
bool ADS1299Plus::readReg(uint8_t addr, uint8_t &value) { return readOne_(addr, value); }

bool ADS1299Plus::writeRegs(uint8_t startAddr, const uint8_t *data, size_t n) { return writeBurst_(startAddr, data, n); }
bool ADS1299Plus::readRegs(uint8_t startAddr, uint8_t *data, size_t n) { return readBurst_(startAddr, data, n); }

// ---- Helpers alto nivel ----
bool ADS1299Plus::setDataRate(uint8_t dr3b)
{
  uint8_t cfg1;
  if (!readReg(ADS_REG_CONFIG1, cfg1))
    return false;
  cfg1 = (cfg1 & 0xF8) | (dr3b & 0x07);
  return writeReg(ADS_REG_CONFIG1, cfg1);
}

bool ADS1299Plus::setClockOut(bool enable)
{
  uint8_t cfg1;
  if (!readReg(ADS_REG_CONFIG1, cfg1))
    return false;
  if (enable)
    cfg1 |= ADS_CFG1_CLK_EN;
  else
    cfg1 &= ~ADS_CFG1_CLK_EN;
  return writeReg(ADS_REG_CONFIG1, cfg1);
}

bool ADS1299Plus::setDaisyEnable(bool enable)
{
  uint8_t cfg1;
  if (!readReg(ADS_REG_CONFIG1, cfg1))
    return false;
  if (enable)
    cfg1 |= ADS_CFG1_DAISY_EN;
  else
    cfg1 &= ~ADS_CFG1_DAISY_EN;
  return writeReg(ADS_REG_CONFIG1, cfg1);
}

bool ADS1299Plus::setChannel(uint8_t ch, uint8_t chsetByte)
{
  if (!validCh_(ch))
    return false;
  return writeReg(chRegAddr_(ch), chsetByte);
}

bool ADS1299Plus::powerDownChannel(uint8_t ch, bool pd)
{
  if (!validCh_(ch))
    return false;
  uint8_t ch_val;
  if (!readReg(chRegAddr_(ch), ch_val))
    return false;
  if (pd)
    ch_val |= ADS_CH_PD;
  else
    ch_val &= ~ADS_CH_PD;
  return writeReg(chRegAddr_(ch), ch_val);
}

bool ADS1299Plus::setChannelGain(uint8_t ch, uint8_t gain3b)
{
  if (!validCh_(ch))
    return false;
  uint8_t ch_val;
  if (!readReg(chRegAddr_(ch), ch_val))
    return false;
  ch_val = (ch_val & 0x8F) | ((gain3b & 0x07) << 4);
  return writeReg(chRegAddr_(ch), ch_val);
}

bool ADS1299Plus::setChannelMux(uint8_t ch, uint8_t mux3b)
{
  if (!validCh_(ch))
    return false;
  uint8_t ch_val;
  if (!readReg(chRegAddr_(ch), ch_val))
    return false;
  ch_val = (ch_val & 0xF8) | (mux3b & 0x07);
  return writeReg(chRegAddr_(ch), ch_val);
}

bool ADS1299Plus::setSRB2(uint8_t ch, bool en)
{
  if (!validCh_(ch))
    return false;
  uint8_t ch_val;
  if (!readReg(chRegAddr_(ch), ch_val))
    return false;
  if (en)
    ch_val |= ADS_CH_SRB2;
  else
    ch_val &= ~ADS_CH_SRB2;
  return writeReg(chRegAddr_(ch), ch_val);
}

bool ADS1299Plus::enableSRB1(bool en)
{
  uint8_t misc1;
  if (!readReg(ADS_REG_MISC1, misc1))
    return false;
  if (en)
    misc1 |= ADS_MISC1_SRB1;
  else
    misc1 &= ~ADS_MISC1_SRB1;
  return writeReg(ADS_REG_MISC1, misc1);
}

bool ADS1299Plus::useInternalRef(bool enBuf)
{
  uint8_t cfg3;
  if (!readReg(ADS_REG_CONFIG3, cfg3))
    return false;
  if (enBuf)
    cfg3 |= ADS_CFG3_PD_REFBUF;
  else
    cfg3 &= ~ADS_CFG3_PD_REFBUF;
  return writeReg(ADS_REG_CONFIG3, cfg3);
}

bool ADS1299Plus::useBiasInternalRef(bool enInt)
{
  uint8_t cfg3;
  if (!readReg(ADS_REG_CONFIG3, cfg3))
    return false;
  if (enInt)
    cfg3 |= ADS_CFG3_BIASREF_INT;
  else
    cfg3 &= ~ADS_CFG3_BIASREF_INT;
  return writeReg(ADS_REG_CONFIG3, cfg3);
}

bool ADS1299Plus::enableBiasBuffer(bool en)
{
  uint8_t cfg3;
  if (!readReg(ADS_REG_CONFIG3, cfg3))
    return false;
  if (en)
    cfg3 |= ADS_CFG3_PD_BIAS;
  else
    cfg3 &= ~ADS_CFG3_PD_BIAS;
  return writeReg(ADS_REG_CONFIG3, cfg3);
}

bool ADS1299Plus::routeBiasSense(bool en)
{
  uint8_t cfg3;
  if (!readReg(ADS_REG_CONFIG3, cfg3))
    return false;
  if (en)
    cfg3 |= ADS_CFG3_BIAS_LOFF_SENS;
  else
    cfg3 &= ~ADS_CFG3_BIAS_LOFF_SENS;
  return writeReg(ADS_REG_CONFIG3, cfg3);
}

bool ADS1299Plus::enableBiasMeasure(bool en)
{
  uint8_t cfg3;
  if (!readReg(ADS_REG_CONFIG3, cfg3))
    return false;
  if (en)
    cfg3 |= ADS_CFG3_BIAS_MEAS;
  else
    cfg3 &= ~ADS_CFG3_BIAS_MEAS;
  return writeReg(ADS_REG_CONFIG3, cfg3);
}

bool ADS1299Plus::configureLeadOff(uint8_t loffByte)
{
  return writeReg(ADS_REG_LOFF, loffByte);
}

bool ADS1299Plus::enableLeadOffSenseP(uint8_t chMask)
{
  return writeReg(ADS_REG_LOFF_SENSP, chMask);
}

bool ADS1299Plus::enableLeadOffSenseN(uint8_t chMask)
{
  return writeReg(ADS_REG_LOFF_SENSN, chMask);
}

bool ADS1299Plus::setLeadOffFlip(uint8_t chMask)
{
  return writeReg(ADS_REG_LOFF_FLIP, chMask);
}

bool ADS1299Plus::setSingleShot(bool singleShot)
{
  uint8_t cfg4;
  if (!readReg(ADS_REG_CONFIG4, cfg4))
    return false;
  if (singleShot)
    cfg4 |= ADS_CFG4_SINGLE_SHOT;
  else
    cfg4 &= ~ADS_CFG4_SINGLE_SHOT;
  return writeReg(ADS_REG_CONFIG4, cfg4);
}

bool ADS1299Plus::enableLoffComparators(bool en)
{
  uint8_t cfg4;
  if (!readReg(ADS_REG_CONFIG4, cfg4))
    return false;
  if (en)
    cfg4 &= ~ADS_CFG4_PD_LOFF_COMP;
  else
    cfg4 |= ADS_CFG4_PD_LOFF_COMP;
  return writeReg(ADS_REG_CONFIG4, cfg4);
}

bool ADS1299Plus::setBiasDeriveP(uint8_t chMask)
{
  return writeReg(ADS_REG_BIAS_SENSP, chMask);
}

bool ADS1299Plus::setBiasDeriveN(uint8_t chMask)
{
  return writeReg(ADS_REG_BIAS_SENSN, chMask);
}

// ---- Lectura de frames ----
bool ADS1299Plus::readFrameRDATAC(uint32_t &status24, int32_t chOut[NUM_CHANNELS])
{
  if (!rdatacActive_)
    return false;

  uint8_t rxBuf[3 + 3 * NUM_CHANNELS];
  spi_.select();
  for (int i = 0; i < (int)sizeof(rxBuf); ++i)
  {
    rxBuf[i] = spi_.xfer(0x00);
  }
  spi_.deselect();

  // Desempaquetar status (primeros 3 bytes)
  status24 = ((uint32_t)rxBuf[0] << 16) | ((uint32_t)rxBuf[1] << 8) | rxBuf[2];

  // Desempaquetar canales (3 bytes por canal)
  for (int i = 0; i < NUM_CHANNELS; ++i)
  {
    chOut[i] = unpack24(&rxBuf[3 + 3 * i]);
  }

  return statusHasSync(status24);
}

bool ADS1299Plus::readDataOnDemand(uint32_t &status24, int32_t chOut[NUM_CHANNELS])
{
  cmdRDATA();

  uint8_t rxBuf[3 + 3 * NUM_CHANNELS];
  spi_.select();
  for (int i = 0; i < (int)sizeof(rxBuf); ++i)
  {
    rxBuf[i] = spi_.xfer(0x00);
  }
  spi_.deselect();

  status24 = ((uint32_t)rxBuf[0] << 16) | ((uint32_t)rxBuf[1] << 8) | rxBuf[2];

  for (int i = 0; i < NUM_CHANNELS; ++i)
  {
    chOut[i] = unpack24(&rxBuf[3 + 3 * i]);
  }

  return statusHasSync(status24);
}

bool ADS1299Plus::readDeviceID(uint8_t &id)
{
  return readReg(ADS_REG_ID, id);
}
