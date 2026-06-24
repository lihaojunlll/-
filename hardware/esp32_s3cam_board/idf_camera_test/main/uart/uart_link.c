#include <stdio.h>
#include <stdint.h>
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_log.h"
#include "app_config.h"

static const char *TAG = "uart";

void uart_link_init(void)
{
    uart_config_t uart_cfg = {
        .baud_rate = UART_BAUDRATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(UART_PORT_NUM, 256, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_PORT_NUM, &uart_cfg));
    ESP_ERROR_CHECK(uart_set_pin(UART_PORT_NUM, UART_TX_PIN, UART_RX_PIN,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_LOGI(TAG, "UART(%d) init: tx=GPIO%d rx=GPIO%d baud=%d",
             UART_PORT_NUM, UART_TX_PIN, UART_RX_PIN, UART_BAUDRATE);
}

void uart_link_send(const char *data, size_t len)
{
    uart_write_bytes(UART_PORT_NUM, data, len);
}

static void uart_link_send_packet(const char *body)
{
    char buf[80];
    uint8_t crc = 0;
    int body_len = 0;
    while (body[body_len] != '\0') {
        body_len++;
    }
    for (int i = 0; i < body_len; i++) {
        crc ^= (uint8_t)body[i];
    }
    int len = snprintf(buf, sizeof(buf), "%s*%02X\n", body, crc);
    uart_write_bytes(UART_PORT_NUM, buf, len);
}

void uart_link_send_imu(int seq, float pitch, float roll, float yaw)
{
    char body[64];
    snprintf(body, sizeof(body), "IMU,%d,%.2f,%.2f,%.2f",
             seq, pitch, roll, yaw);
    uart_link_send_packet(body);
}

void uart_link_send_camera(int seq, float near_x, float far_x,
                           float curve, float quality)
{
    char body[80];
    snprintf(body, sizeof(body), "CAM,%d,%.2f,%.2f,%.2f,%.2f",
             seq, near_x, far_x, curve, quality);
    uart_link_send_packet(body);
}
