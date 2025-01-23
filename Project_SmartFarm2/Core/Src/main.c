/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * @file           : main.c
 * @brief          : Main program body
 ******************************************************************************
 * @attention
 *
 * Copyright (c) 2025 STMicroelectronics.
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 * If no LICENSE file comes with this software, it is provided AS-IS.
 *
 ******************************************************************************
 */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "dma.h"
#include "i2c.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

#include "dht.h"
#include "I2C_LCD.h"

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

#ifdef __GNUC__
/* With GCC, small printf (option LD Linker->Libraries->Small printf
     set to 'Yes') calls __io_putchar() */
#define PUTCHAR_PROTOTYPE int __io_putchar(int ch)
#else
#define PUTCHAR_PROTOTYPE int fputc(int ch, FILE *f)
#endif /* __GNUC__ */
PUTCHAR_PROTOTYPE
{
  /* Place your implementation of fputc here */
  /* e.g. write a character to the EVAL_COM1 and Loop until the end of transmission */
  HAL_UART_Transmit(&huart2, (uint8_t *)&ch, 1, 0xFFFF);

  return ch;
}

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

DHT11 dht;
char lcdBuffer[16];
volatile uint16_t adcValue[2];

#define Light       (adcValue[0]) // ADC값 배열0번 조도
#define WaterLevel  (adcValue[1]) // ADC값 배열1번 수위

// 물 수위 설정 전 코드
// volatile uint16_t adcValue;
// volatile uint16_t adcValue2;

uint8_t adcFlag = 0;
uint8_t rxData;
uint64_t WaterPumpCounter = 0;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
void Command(uint8_t Data);
void Command(uint8_t Data)
{
  if(Data == 'L')// LED ON
  {
    HAL_GPIO_WritePin(LED_R_GPIO_Port, LED_R_Pin, 1);
    HAL_GPIO_WritePin(LED_G_GPIO_Port, LED_G_Pin, 1);
    HAL_GPIO_WritePin(LED_B_GPIO_Port, LED_B_Pin, 1);
    HAL_UART_Transmit(&huart1, (uint8_t *)"LED ON",
                      strlen("LED ON"), 0xFFFF);

  }

  if(Data == 'l')// LED OFF
  {
    HAL_GPIO_WritePin(LED_R_GPIO_Port, LED_R_Pin, 0);
    HAL_GPIO_WritePin(LED_G_GPIO_Port, LED_G_Pin, 0);
    HAL_GPIO_WritePin(LED_B_GPIO_Port, LED_B_Pin, 0);
    HAL_UART_Transmit(&huart1, (uint8_t *)"LED OFF",
                      strlen("LED OFF"), 0xFFFF);

  }

  if(Data == 'P')//Pump ON
  {
    HAL_GPIO_WritePin(Pump_GPIO_Port, Pump_Pin, 1);
    HAL_GPIO_WritePin(Pump2_GPIO_Port, Pump2_Pin, 0);
    HAL_UART_Transmit(&huart1, (uint8_t *)"Pump ON",
                      strlen("Pump ON"), 0xFFFF);
    //      HAL_TIM_Base_Start_IT(&htim3);
  }

  if(Data == 'p')//Pump OFF
  {
    //      __HAL_TIM_SET_COUNTER(&htim3, 0);
    //      HAL_TIM_Base_Stop_IT(&htim3);
    HAL_GPIO_WritePin(Pump_GPIO_Port, Pump_Pin, 0);
    HAL_GPIO_WritePin(Pump2_GPIO_Port, Pump2_Pin, 0);
    HAL_UART_Transmit(&huart1, (uint8_t *)"Pump OFF",
                      strlen("Pump OFF"), 0xFFFF);
  }

  if(Data == 'F')// FAN ON
  {
    TIM2->CCR1 = 65535;
    HAL_UART_Transmit(&huart1, (uint8_t *)"Fan ON",
                      strlen("Fan ON"), 0xFFFF);
  }

  if(Data == 'f')// FAN OFF
  {
    TIM2->CCR1 = 0;
    HAL_UART_Transmit(&huart1, (uint8_t *)"Fan OFF",
                      strlen("Fan OFF"), 0xFFFF);
  }

  if(Data == 'E')//EMERGENCY
  {
    HAL_GPIO_WritePin(LED_R_GPIO_Port, LED_R_Pin, 1);
    HAL_GPIO_WritePin(LED_G_GPIO_Port, LED_G_Pin, 0);
    HAL_GPIO_WritePin(LED_B_GPIO_Port, LED_B_Pin, 0);
    HAL_UART_Transmit(&huart1, (uint8_t *)"Emergency",
                      strlen("Emergency"), 0xFFFF);
  }

}

void updateLCD(void)
{
  lcdCommand(CLEAR_DISPLAY);
  HAL_Delay(2);  // Clear 명령 후 잠시 대기

  // 첫 번째 줄: 온도와 습도
  sprintf(lcdBuffer, "Temp:%dC ", dht.temperature);
  moveCursor(0, 0); // 첫번째줄 첫번째 시작
  lcdString(lcdBuffer);
  HAL_Delay(1);

  // 두 번째 줄: 조도값
  sprintf(lcdBuffer, "Humi:%d%%", dht.humidity); // 값바꿔줌
  moveCursor(1, 0); // 두번째줄 첫번째 시작
  lcdString(lcdBuffer);
}

void DHT_Reset(); // 온습도 사이클 조정
void DHT_Reset()
{
  dht11GpioMode(&dht, OUTPUT);
  HAL_GPIO_WritePin(dht.port, dht.pin, GPIO_PIN_SET);
}

// ADC 변환 완료 콜백
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc)
{
  if(hadc->Instance == ADC1)
  {
    adcFlag = 1;  // ADC 변환 완료 플래그 설정
  }
}


void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if(huart->Instance == USART1) // 유아트1(블루투스)에 송신 되었을 때
  {
    //HAL_UART_Transmit_IT(&huart1, &rxData, sizeof(rxData));

    Command(rxData); // 값 입력시 출력 함수
    HAL_UART_Receive_IT(&huart1, &rxData, sizeof(rxData));
    // 다시 수신 대기상태


  }

  if(huart->Instance == USART2) // 유아트2(라즈베리)에 송신 되었을 때
  {

    Command(rxData); // 값 입력시 출력 함수
    HAL_UART_Receive_IT(&huart2, &rxData, sizeof(rxData));
    // 다시 수신 대기상태
  }
}

//  void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
//  {
//    if (htim->Instance == TIM3)//모터 회전하라는 타이머 플레그가 세워지면
//    {
//
//      if(WaterPumpCounter >= 3)
//      {
//        WaterPumpCounter = 0;
//        __HAL_TIM_SET_COUNTER(&htim3, 0);
//        HAL_TIM_Base_Stop_IT(&htim3);
//        HAL_GPIO_WritePin(Pump_GPIO_Port, Pump_Pin, 0);
//      }
//      WaterPumpCounter++;
//    }
//  }


/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
 * @brief  The application entry point.
 * @retval int
 */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART2_UART_Init();
  MX_ADC1_Init();
  MX_I2C1_Init();
  MX_TIM2_Init();
  MX_TIM11_Init();
  MX_TIM3_Init();
  MX_USART1_UART_Init();
  /* USER CODE BEGIN 2 */

  // 마이크로초 타이머 시작
  //  HAL_TIM_Base_Start(&htim11);
  //  HAL_Delay(100);  // 타이머 안정화 대기

  // LCD 초기화 전 충분한 대기시간
  // HAL_Delay(1000);
  lcdInit();
  HAL_Delay(200);
  // LCD 초기화 후 충분히 대기

  // LCD 테스트
  lcdCommand(CLEAR_DISPLAY);
  HAL_Delay(2);
  moveCursor(0, 0);
  lcdString("System Start...");
  HAL_Delay(1000); // 딜레이 빼면 안됨..

  // 온습도센서 Init , 초기화 및 GPIO 설정
  dht11Init(&dht, GPIOC, GPIO_PIN_4);

  // ADC로 저항값을 DMA로 받기위한 대기상태
  HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adcValue, 2);
  //HAL_ADC_Start_DMA(&hadc1, (uint32_t*)&adcValue, 1);

  // 유아트 대기상태 ( 버튼 클릭시 유아트 필요 )
  HAL_UART_Receive_IT(&huart2, &rxData, sizeof(rxData));
  HAL_UART_Receive_IT(&huart1, &rxData, sizeof(rxData));

  // TIM3 PWM 시작 (DC 팬 모터용)
  HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
  // __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, 60000);



  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */

  dht11GpioMode(&dht, OUTPUT);
  HAL_GPIO_WritePin(dht.port, dht.pin, GPIO_PIN_SET);
  HAL_Delay(1000); // DHT11 안정화 대기


  while (1)
  {
    // DHT11 데이터 읽기 시도
    if(dht11Read(&dht))
    {
      // UART로 온습도와 조도값 전송
      printf("%d, %d, %d\n",
             dht.temperature,
             dht.humidity,
             Light);

      updateLCD();  // LCD 업데이트 현재 상태로 업데이트

      //        if(dht.temperature > 28)
      //        {
      //          TIM2->CCR1 = 65535;
      //        }
      //
      //
      //        if (Light < 1000)
      //        {
      //          HAL_GPIO_WritePin(LED_B_GPIO_Port, LED_B_Pin, 1);
      //
      //          HAL_GPIO_WritePin(Pump_GPIO_Port, Pump_Pin, 1);
      //          HAL_TIM_Base_Start_IT(&htim3);
      //
      //        }

      // 온습도 측정 포트설정 리셋
      DHT_Reset();
      HAL_Delay(2000);  // 2초 주기로 반복
      // ADC로 저항값을 DMA로 '다시' 받기위한 대기상태
      HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adcValue, 2);

      //HAL_ADC_Start_DMA(&hadc1, (uint32_t*)&adcValue, 1);
    }


    else
    {
      printf("DHT11 Read Failed\r\n");
      // DHT11 리셋을 위한 처리
      DHT_Reset();
      HAL_Delay(1000);
    }

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
 * @brief System Clock Configuration
 * @retval None
 */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
   */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
   * in the RCC_OscInitTypeDef structure.
   */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 100;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 4;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
   */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
      |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_3) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */



/* USER CODE END 4 */

/**
 * @brief  This function is executed in case of error occurrence.
 * @retval None
 */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
 * @brief  Reports the name of the source file and the source line number
 *         where the assert_param error has occurred.
 * @param  file: pointer to the source file name
 * @param  line: assert_param error line source number
 * @retval None
 */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
