idf_component_register(SRCS "main.c"
                           "wifi/wifi_ap.c"
                           "camera/camera_web.c"
                           "imu/imu.c"
                           "uart/uart_link.c"
                    INCLUDE_DIRS "."
                    REQUIRES esp_driver_i2c esp_driver_uart esp_http_server esp_wifi esp_netif nvs_flash esp_timer)
