#pragma once

#define WIFI_AP_SSID      "S3CAM"
#define WIFI_AP_PASSWORD  ""
#define WIFI_AP_CHANNEL   6
#define WIFI_AP_MAX_CONN  4

#define CAM_PIN_PWDN   -1
#define CAM_PIN_RESET  -1
#define CAM_PIN_XCLK   15
#define CAM_PIN_SIOD   4
#define CAM_PIN_SIOC   5

#define CAM_PIN_D7     16
#define CAM_PIN_D6     17
#define CAM_PIN_D5     18
#define CAM_PIN_D4     12
#define CAM_PIN_D3     10
#define CAM_PIN_D2     8
#define CAM_PIN_D1     9
#define CAM_PIN_D0     11
#define CAM_PIN_VSYNC  6
#define CAM_PIN_HREF   7
#define CAM_PIN_PCLK   13

#define I2C_MASTER_NUM     I2C_NUM_0
#define I2C_MASTER_SCL_IO  21
#define I2C_MASTER_SDA_IO  47
#define I2C_MASTER_FREQ_HZ 100000
#define MPU6050_ADDR_LOW   0x68
#define MPU6050_ADDR_HIGH  0x69

#define MPU6050_REG_PWR_MGMT_1   0x6B
#define MPU6050_REG_ACCEL_CONFIG 0x1C
#define MPU6050_REG_GYRO_CONFIG  0x1B
#define MPU6050_REG_ACCEL_XOUT_H 0x3B
#define MPU6050_REG_GYRO_XOUT_H  0x43
#define MPU6050_REG_WHO_AM_I     0x75

#define ACCEL_SCALE  16384.0f
#define GYRO_SCALE   131.0f

#define UART_PORT_NUM   UART_NUM_1
#define UART_TX_PIN     45
#define UART_RX_PIN     46
#define UART_BAUDRATE   115200

#define ATTITUDE_ALPHA       0.96f
#define CONTROL_PERIOD_MS    10
#define IMU_PRINT_PERIOD_MS  200
