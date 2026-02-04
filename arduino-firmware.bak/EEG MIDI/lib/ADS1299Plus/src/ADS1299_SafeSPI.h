// ADS1299_SafeSPI.h
// Wrapper SPI seguro con timing y control de CS

#pragma once
#include <Arduino.h>
#include <SPI.h>

class ADS1299_SafeSPI
{
public:
  explicit ADS1299_SafeSPI(uint8_t csPin);

  void begin();
  void end();

  void select();
  void deselect();

  uint8_t xfer(uint8_t data);
  void waitDecode(); // asegura tSDECODE >= 4 tCLK (~2 µs mínimo)

private:
  uint8_t csPin_;
};
