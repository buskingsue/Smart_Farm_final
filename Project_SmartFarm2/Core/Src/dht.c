#include "dht.h"

void dht11Init(DHT11 *dht, GPIO_TypeDef *port, uint16_t pin)
{
  dht->port = port;
  dht->pin = pin;
}

// DHT11 GPIO Mode 함수 설정
void dht11GpioMode(DHT11 *dht, uint8_t mode)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};  //GPIO 구조체 변수 선언 및 초기화


  if(mode == OUTPUT)
  {
    // 출력모드 설정
    GPIO_InitStruct.Pin = dht->pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(dht->port, &GPIO_InitStruct);
  }
  else if(mode == INPUT)
  {
    // 입력모드 설정
    GPIO_InitStruct.Pin = dht->pin;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(dht->port, &GPIO_InitStruct);
  }
}
uint8_t dht11Read(DHT11 *dht)
{
  bool ret = true;    //  기본 반환값 설정

  uint16_t timeTick = 0;     //시간 측정 변수 선언 및 초기화
  uint8_t  pluse[40] = {0};  // 40비트 데이터를 저장...

  uint8_t humValue1 = 0, humValue2 = 0;
  uint8_t tempValue1 = 0, tempValue2 = 0;
  uint8_t parityValue = 0;

  // 타이머 시작
  HAL_TIM_Base_Start(&htim11);

  // 통신 시작 신호 전송
  dht11GpioMode(dht, OUTPUT);       //GPIO를 출력으로 선언
  HAL_GPIO_WritePin(dht->port, dht->pin, 0);
  HAL_Delay(20);                    // 적어도 18ms 이상 대기
  HAL_GPIO_WritePin(dht->port, dht->pin, 1);
  delay_us(20);
  dht11GpioMode(dht, INPUT);        //INPUT 모드로 전환


  //  DHT11의 응답신호 대기
  __HAL_TIM_SET_COUNTER(&htim11, 0);
  while(HAL_GPIO_ReadPin(dht->port, dht->pin) == GPIO_PIN_RESET)
  {
    if(__HAL_TIM_GET_COUNTER(&htim11) > 100)
    {
      printf("LOW Signal Time Out\n\r");
      break;
    }
  }
  __HAL_TIM_SET_COUNTER(&htim11, 0);
  while(HAL_GPIO_ReadPin(dht->port, dht->pin) == GPIO_PIN_SET)
  {
    if(__HAL_TIM_GET_COUNTER(&htim11) > 120)
    {
      printf("HIGH Signal Time Out\n\r");
      break;
    }
  }

  for(uint8_t i= 0; i <40; i++)
  {
    while(HAL_GPIO_ReadPin(dht->port, dht->pin) == GPIO_PIN_RESET);

    __HAL_TIM_SET_COUNTER(&htim11, 0);
    while(HAL_GPIO_ReadPin(dht->port, dht->pin) == GPIO_PIN_SET)
    {
      timeTick = __HAL_TIM_GET_COUNTER(&htim11);

      //  신호 길이 판별
      if(timeTick > 20 && timeTick < 30)    // 26 ~ 28us -> '0'
      {
        pluse[i] = 0;
      }
      else if(timeTick > 65 && timeTick < 85)
      {
        pluse[i] = 1;
      }
    }
  }
  HAL_TIM_Base_Stop(&htim11);

  // 온습도 데이터 처리
  for(uint8_t i = 0; i < 8; i++) {humValue1 = (humValue1 << 1) + pluse[i];} // 습도 상위 8비트
  for(uint8_t i = 8; i < 16; i++) {humValue2 = (humValue2 << 1) + pluse[i];} // 습도 하위 8비트
  for(uint8_t i = 16; i < 24; i++) {tempValue1 = (tempValue1 << 1) + pluse[i];} // 온도 상위 8비트
  for(uint8_t i = 24; i < 32; i++) {tempValue2 = (tempValue2 << 1) + pluse[i];} // 온도 하위 8비트
  for(uint8_t i = 32; i < 40; i++) {parityValue = (parityValue << 1) + pluse[i];}

  // 구조체에 온습도 값 저장
  dht->temperature = tempValue1;
  dht->humidity = humValue1;


  uint8_t checkSum = humValue1 + humValue2 + tempValue1 + tempValue2;
  if(checkSum != parityValue)
  {
    printf("Checksum Error\r\n");
  }





  return ret;
}
