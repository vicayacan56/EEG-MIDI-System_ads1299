// ADS1299_SafeSPI.cpp

#include "ADS1299_SafeSPI.h"

ADS1299_SafeSPI::ADS1299_SafeSPI(uint8_t csPin) : csPin_(csPin) {}

void ADS1299_SafeSPI::begin()
{
  pinMode(csPin_, OUTPUT);
  digitalWrite(csPin_, HIGH);

  SPI.begin();
  SPI.beginTransaction(SPISettings(2000000, MSBFIRST, SPI_MODE1));
}

void ADS1299_SafeSPI::end()
{
  SPI.endTransaction();
  SPI.end();
}

void ADS1299_SafeSPI::select()
{
  digitalWrite(csPin_, LOW);
}

void ADS1299_SafeSPI::deselect()
{
  digitalWrite(csPin_, HIGH);
}

uint8_t ADS1299_SafeSPI::xfer(uint8_t data)
{
  return SPI.transfer(data);
}

void ADS1299_SafeSPI::waitDecode()
{
  // tSDECODE = ≥4 tCLK. A 2.048 MHz, tCLK≈488 ns → 4*tCLK≈2 µs.
  delayMicroseconds(3);
}
