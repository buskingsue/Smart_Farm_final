#include "I2C_LCD.h"
//핸들러 정의

extern I2C_HandleTypeDef hi2c1; //i2c.c 소스파일에 정의되어있음

void lcdCommand(uint8_t command)
{
  uint8_t high_nibble, low_nibble;
  uint8_t i2c_buffer[4];
  high_nibble = command & 0xf0;
  low_nibble = (command << 4) & 0xf0;
  i2c_buffer[0] = high_nibble | 0x04 | 0x08;
  i2c_buffer[1] = high_nibble | 0x00 | 0x08;
  i2c_buffer[2] = low_nibble | 0x04 | 0x08;
  i2c_buffer[3] = low_nibble | 0x00 | 0x08;
  while(HAL_I2C_Master_Transmit(&hi2c1, I2C_LCD_ADDRESS, i2c_buffer,
                                4, 100) != HAL_OK);
}

//1byte write

void lcdData(uint8_t data)
{
  uint8_t high_nibble, low_nibble;
  uint8_t i2c_buffer[4];
  high_nibble = data & 0xf0;
  low_nibble = (data << 4) & 0xf0;
  i2c_buffer[0] = high_nibble | 0x05 | 0x08;
  i2c_buffer[1] = high_nibble | 0x01 | 0x08;
  i2c_buffer[2] = low_nibble | 0x05 | 0x08;
  i2c_buffer[3] = low_nibble | 0x01 | 0x08;
  while(HAL_I2C_Master_Transmit(&hi2c1, I2C_LCD_ADDRESS, i2c_buffer,
                                4, 100) != HAL_OK);
}
void lcdInit(void)
{
  HAL_Delay(50);
  lcdCommand(0x33);
  HAL_Delay(5);
  lcdCommand(0x32);
  HAL_Delay(5);
  lcdCommand(0x28);
  HAL_Delay(5);
  lcdCommand(DISPLAY_ON);
  HAL_Delay(5);
  lcdCommand(0x06);
  HAL_Delay(5);
  lcdCommand(CLEAR_DISPLAY);
  HAL_Delay(2);
}
void lcdString(char *str)
{
  while(*str)lcdData(*str++);
}

void moveCursor(uint8_t row, uint8_t col)
{
  lcdCommand(0x80 | row<<6 | col);
}
