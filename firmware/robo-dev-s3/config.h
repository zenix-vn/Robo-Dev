#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

// Board: ESP32-S3-N16R8 dual USB-C devkit (no camera) + INMP441 + MAX98357A
//        + ST7789 1.54" 240x240 (7 pin) + L9110S motor driver + VL6180X
// Pinout follows so-do-mach/1789757351520_esp.jpg

#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 24000

#define AUDIO_I2S_METHOD_SIMPLEX

// INMP441 microphone (soldered on the back of the board; differs from so-do-mach)
#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_4
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_5
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_6   // SD

// MAX98357A amplifier (soldered on the back of the board; differs from so-do-mach, which uses 39/40/41)
#define AUDIO_I2S_SPK_GPIO_DOUT GPIO_NUM_7   // DIN
#define AUDIO_I2S_SPK_GPIO_BCLK GPIO_NUM_15  // BCLK
#define AUDIO_I2S_SPK_GPIO_LRCK GPIO_NUM_16  // LRC

#define BUILTIN_LED_GPIO        GPIO_NUM_48  // onboard RGB (WS2812)
#define BOOT_BUTTON_GPIO        GPIO_NUM_0
#define TOUCH_BUTTON_GPIO       GPIO_NUM_NC
#define VOLUME_UP_BUTTON_GPIO   GPIO_NUM_NC
#define VOLUME_DOWN_BUTTON_GPIO GPIO_NUM_NC

// ST7789 240x240 (GND VCC SCL SDA RES DC CS BLK); CS is tied to GND, BLK to 3V3
// DC/RST use GPIO43/44 (UART0 TX/RX), so the console runs over native USB (USB-Serial/JTAG);
// the CH343 COM port is only used for flashing
#define DISPLAY_BACKLIGHT_PIN GPIO_NUM_NC
#define DISPLAY_MOSI_PIN      GPIO_NUM_1   // SDA
#define DISPLAY_CLK_PIN       GPIO_NUM_2   // SCL
#define DISPLAY_DC_PIN        GPIO_NUM_43  // wired to TX
#define DISPLAY_RST_PIN       GPIO_NUM_44  // wired to RX
#define DISPLAY_CS_PIN        GPIO_NUM_NC

#define DISPLAY_WIDTH   240
#define DISPLAY_HEIGHT  240
#define DISPLAY_MIRROR_X false
#define DISPLAY_MIRROR_Y false
#define DISPLAY_SWAP_XY false
#define DISPLAY_INVERT_COLOR    true
#define DISPLAY_RGB_ORDER  LCD_RGB_ELEMENT_ORDER_RGB
#define DISPLAY_OFFSET_X  0
#define DISPLAY_OFFSET_Y  0
#define DISPLAY_BACKLIGHT_OUTPUT_INVERT false
#define DISPLAY_SPI_MODE 3  // 7-pin module without CS
#define DISPLAY_SPI_CLOCK_HZ (10 * 1000 * 1000)  // low clock: tolerant of long jumper wires

// Motor driver (2 channels, 4 inputs, driven with PWM so speed can be controlled)
// Do not use GPIO19/20 (native USB, console and Robo Dev link) or GPIO43/44 (LCD DC/RST).
#define ROBOT_ENABLE_MOTORS 1
// GPIO4/5 are used by the microphone, so motor A moved to GPIO17/18
#define MOTOR_A_IN1_GPIO GPIO_NUM_17
#define MOTOR_A_IN2_GPIO GPIO_NUM_18
#define MOTOR_B_IN3_GPIO GPIO_NUM_3
#define MOTOR_B_IN4_GPIO GPIO_NUM_14

// VL6180X distance sensor (I2C, ranges about 0-100 mm)
#define SENSOR_I2C_SDA_GPIO GPIO_NUM_12
#define SENSOR_I2C_SCL_GPIO GPIO_NUM_13
// Stop when moving forward and an obstacle is closer than this
#define OBSTACLE_STOP_DISTANCE_MM 150

// Robot personality
#define ROBOT_NAME "Robo"
// Minimum time between two "obstacle" reports sent to the AI (ms)
#define OBSTACLE_REPORT_INTERVAL_MS 20000

#endif // _BOARD_CONFIG_H_
