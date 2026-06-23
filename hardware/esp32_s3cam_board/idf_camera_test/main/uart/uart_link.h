#pragma once

void uart_link_init(void);
void uart_link_send(const char *data, size_t len);
void uart_link_send_imu(int seq, float pitch, float roll, float yaw);
