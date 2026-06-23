#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <math.h>

#include "driver/ledc.h"
#include "driver/i2c_master.h"
#include "driver/uart.h"
#include "esp_camera.h"
#include "esp_err.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

static const char *TAG = "s3cam_web";
static const char *IMU_TAG = "imu";

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

#define I2C_MASTER_NUM         I2C_NUM_0
#define I2C_MASTER_SCL_IO      21
#define I2C_MASTER_SDA_IO      47
#define I2C_MASTER_FREQ_HZ     100000
#define MPU6050_ADDR_LOW       0x68
#define MPU6050_ADDR_HIGH      0x69

#define MPU6050_REG_PWR_MGMT_1   0x6B
#define MPU6050_REG_ACCEL_CONFIG 0x1C
#define MPU6050_REG_GYRO_CONFIG  0x1B
#define MPU6050_REG_ACCEL_XOUT_H 0x3B
#define MPU6050_REG_GYRO_XOUT_H  0x43
#define MPU6050_REG_WHO_AM_I     0x75

#define ACCEL_SCALE  16384.0f
#define GYRO_SCALE   131.0f

#define UART_PORT_NUM    UART_NUM_1
#define UART_TX_PIN      45
#define UART_RX_PIN      46
#define UART_BAUDRATE    115200

#define ATTITUDE_ALPHA       0.96f
#define CONTROL_PERIOD_MS    10
#define IMU_PRINT_PERIOD_MS  200

static float ax_off = 0, ay_off = 0, az_off = 0;
static float gx_off = 0, gy_off = 0, gz_off = 0;
static float az_scale = 1.0f;

static float pitch = 0, roll = 0, yaw = 0;
static int64_t last_time_us = 0;

static camera_config_t camera_config = {
    .pin_pwdn = CAM_PIN_PWDN,
    .pin_reset = CAM_PIN_RESET,
    .pin_xclk = CAM_PIN_XCLK,
    .pin_sccb_sda = CAM_PIN_SIOD,
    .pin_sccb_scl = CAM_PIN_SIOC,

    .pin_d7 = CAM_PIN_D7,
    .pin_d6 = CAM_PIN_D6,
    .pin_d5 = CAM_PIN_D5,
    .pin_d4 = CAM_PIN_D4,
    .pin_d3 = CAM_PIN_D3,
    .pin_d2 = CAM_PIN_D2,
    .pin_d1 = CAM_PIN_D1,
    .pin_d0 = CAM_PIN_D0,
    .pin_vsync = CAM_PIN_VSYNC,
    .pin_href = CAM_PIN_HREF,
    .pin_pclk = CAM_PIN_PCLK,

    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG,
    .frame_size = FRAMESIZE_QVGA,
    .jpeg_quality = 12,
    .fb_count = 2,
    .fb_location = CAMERA_FB_IN_PSRAM,
    .grab_mode = CAMERA_GRAB_LATEST,
};

static const char INDEX_HTML[] =
    "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>ESP32-S3 Camera</title>"
    "<style>body{margin:0;font-family:Arial,sans-serif;background:#111;color:#eee;text-align:center}"
    "header{padding:14px;background:#1d1d1d}img{max-width:100%;height:auto;background:#000}"
    "a,button{display:inline-block;margin:10px;padding:10px 14px;border-radius:6px;background:#2d7df6;color:white;text-decoration:none;border:0}"
    ".wrap{padding:12px}</style></head><body>"
    "<header><h2>ESP32-S3 OV3660 Camera</h2></header>"
    "<div class='wrap'><img id='view' src='/stream'>"
    "<p><a href='/jpg' target='_blank'>Open Snapshot</a>"
    "<button onclick=\"document.getElementById('view').src='/jpg?t='+Date.now()\">Snapshot Mode</button>"
    "<button onclick=\"document.getElementById('view').src='/stream?t='+Date.now()\">Stream Mode</button></p>"
    "<p>Connect to Wi-Fi: S3CAM, then open http://192.168.4.1/</p>"
    "</div></body></html>";

static i2c_master_bus_handle_t i2c_bus;
static i2c_master_dev_handle_t i2c_dev;
static uint8_t mpu6050_addr = MPU6050_ADDR_LOW;

static void i2c_master_init(void)
{
    i2c_master_bus_config_t bus_cfg = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .i2c_port = I2C_MASTER_NUM,
        .scl_io_num = I2C_MASTER_SCL_IO,
        .sda_io_num = I2C_MASTER_SDA_IO,
        .glitch_ignore_cnt = 7,
        .intr_priority = 0,
        .flags.enable_internal_pullup = true,
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &i2c_bus));
    ESP_LOGI(IMU_TAG, "I2C(%d) init: scl=GPIO%d sda=GPIO%d freq=%d",
             I2C_MASTER_NUM, I2C_MASTER_SCL_IO, I2C_MASTER_SDA_IO,
             I2C_MASTER_FREQ_HZ);
}

static esp_err_t i2c_read_regs(uint8_t reg, uint8_t *data, size_t len)
{
    memset(data, 0, len);

    esp_err_t ret = i2c_master_transmit(i2c_dev, &reg, 1, pdMS_TO_TICKS(200));
    if (ret != ESP_OK) {
        return ret;
    }

    vTaskDelay(pdMS_TO_TICKS(2));
    return i2c_master_receive(i2c_dev, data, len, pdMS_TO_TICKS(200));
}

static esp_err_t i2c_write_reg(uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = {reg, val};
    return i2c_master_transmit(i2c_dev, buf, sizeof(buf), pdMS_TO_TICKS(100));
}

static bool mpu6050_attach_device(void)
{
    const uint8_t candidates[] = {MPU6050_ADDR_LOW, MPU6050_ADDR_HIGH};
    for (size_t i = 0; i < sizeof(candidates); i++) {
        uint8_t addr = candidates[i];
        i2c_device_config_t dev_cfg = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address = addr,
            .scl_speed_hz = I2C_MASTER_FREQ_HZ,
        };
        esp_err_t add_ret = i2c_master_bus_add_device(i2c_bus, &dev_cfg, &i2c_dev);
        if (add_ret != ESP_OK) {
            ESP_LOGE(IMU_TAG, "Add I2C device 0x%02X failed: %s", addr, esp_err_to_name(add_ret));
            continue;
        }

        vTaskDelay(pdMS_TO_TICKS(20));
        uint8_t who = 0;
        esp_err_t ret = i2c_read_regs(MPU6050_REG_WHO_AM_I, &who, 1);
        ESP_LOGI(IMU_TAG, "I2C read WHO_AM_I at 0x%02X: %s, value=0x%02X",
                 addr, esp_err_to_name(ret), who);
        if (ret == ESP_OK && who == 0x68) {
            mpu6050_addr = addr;
            ESP_LOGI(IMU_TAG, "MPU6050 attached at I2C address 0x%02X", mpu6050_addr);
            return true;
        }

        ESP_ERROR_CHECK_WITHOUT_ABORT(i2c_master_bus_rm_device(i2c_dev));
        i2c_dev = NULL;
    }

    ESP_LOGE(IMU_TAG, "MPU6050 not found at 0x68 or 0x69. Camera web server will keep running.");
    return false;
}

static void mpu6050_write_reg(uint8_t reg, uint8_t val)
{
    esp_err_t ret = i2c_write_reg(reg, val);
    if (ret != ESP_OK) {
        ESP_LOGE(IMU_TAG, "I2C write reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
    }
}

static esp_err_t mpu6050_read_regs(uint8_t reg, uint8_t *data, size_t len)
{
    esp_err_t ret = i2c_read_regs(reg, data, len);
    if (ret != ESP_OK) {
        ESP_LOGE(IMU_TAG, "I2C read reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
    }
    return ret;
}

static uint8_t mpu6050_whoami(void)
{
    uint8_t who = 0;
    mpu6050_read_regs(MPU6050_REG_WHO_AM_I, &who, 1);
    return who;
}

static void mpu6050_init_sensor(void)
{
    mpu6050_write_reg(MPU6050_REG_PWR_MGMT_1, 0x00);
    vTaskDelay(pdMS_TO_TICKS(100));
    mpu6050_write_reg(MPU6050_REG_ACCEL_CONFIG, 0x00);
    mpu6050_write_reg(MPU6050_REG_GYRO_CONFIG, 0x00);
}

static bool mpu6050_read_raw(float *ax, float *ay, float *az, float *gx, float *gy, float *gz)
{
    uint8_t data[14];
    if (mpu6050_read_regs(MPU6050_REG_ACCEL_XOUT_H, data, 14) != ESP_OK) {
        return false;
    }

    *ax = (int16_t)((data[0] << 8) | data[1]) / ACCEL_SCALE;
    *ay = (int16_t)((data[2] << 8) | data[3]) / ACCEL_SCALE;
    *az = (int16_t)((data[4] << 8) | data[5]) / ACCEL_SCALE;
    *gx = (int16_t)((data[8] << 8) | data[9]) / GYRO_SCALE;
    *gy = (int16_t)((data[10] << 8) | data[11]) / GYRO_SCALE;
    *gz = (int16_t)((data[12] << 8) | data[13]) / GYRO_SCALE;
    return true;
}

static void mpu6050_calibrate(int samples)
{
    float sum_ax = 0, sum_ay = 0, sum_az = 0;
    float sum_gx = 0, sum_gy = 0, sum_gz = 0;
    int valid = 0;

    while (valid < samples) {
        float ax, ay, az, gx, gy, gz;
        if (!mpu6050_read_raw(&ax, &ay, &az, &gx, &gy, &gz)) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }
        sum_ax += ax;
        sum_ay += ay;
        sum_az += az;
        sum_gx += gx;
        sum_gy += gy;
        sum_gz += gz;
        valid++;
        vTaskDelay(pdMS_TO_TICKS(2));
    }

    ax_off = sum_ax / samples;
    ay_off = sum_ay / samples;
    az_off = sum_az / samples - 1.0f;
    az_scale = 1.0f;
    gx_off = sum_gx / samples;
    gy_off = sum_gy / samples;
    gz_off = sum_gz / samples;

    ESP_LOGI(IMU_TAG, "Calibrated %d samples, offsets: ax=%.4f ay=%.4f az=%.4f gx=%.4f gy=%.4f gz=%.4f",
             samples, ax_off, ay_off, az_off, gx_off, gy_off, gz_off);
}

static bool mpu6050_read(float *ax, float *ay, float *az, float *gx, float *gy, float *gz)
{
    if (!mpu6050_read_raw(ax, ay, az, gx, gy, gz)) {
        return false;
    }
    *ax = *ax - ax_off;
    *ay = *ay - ay_off;
    *az = (*az - az_off) * az_scale;
    *gx = *gx - gx_off;
    *gy = *gy - gy_off;
    *gz = *gz - gz_off;
    return true;
}

static void uart_init(void)
{
    uart_config_t uart_config = {
        .baud_rate = UART_BAUDRATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(UART_PORT_NUM, 256, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_PORT_NUM, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(UART_PORT_NUM, UART_TX_PIN, UART_RX_PIN,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_LOGI(IMU_TAG, "UART(%d) init: tx=GPIO%d rx=GPIO%d baud=%d",
             UART_PORT_NUM, UART_TX_PIN, UART_RX_PIN, UART_BAUDRATE);
}

static float wrap_180(float angle)
{
    float r = fmodf(angle + 180.0f, 360.0f);
    if (r < 0) r += 360.0f;
    return r - 180.0f;
}

static void attitude_update(float ax, float ay, float az, float gx, float gy, float gz, float dt)
{
    float acc_pitch = atan2f(-ax, sqrtf(ay * ay + az * az)) * 57.2958f;
    float acc_roll = atan2f(ay, az) * 57.2958f;

    pitch = ATTITUDE_ALPHA * (pitch + gx * dt) + (1.0f - ATTITUDE_ALPHA) * acc_pitch;
    roll = ATTITUDE_ALPHA * (roll + gy * dt) + (1.0f - ATTITUDE_ALPHA) * acc_roll;
    yaw += gz * dt;

    pitch = wrap_180(pitch);
    roll = wrap_180(roll);
    yaw = wrap_180(yaw);
}

static void imu_task(void *arg)
{
    mpu6050_init_sensor();
    vTaskDelay(pdMS_TO_TICKS(300));

    uint8_t who = mpu6050_whoami();
    ESP_LOGI(IMU_TAG, "MPU6050 WHO_AM_I: 0x%02X (expected 0x68)", who);
    if (who != 0x68) {
        ESP_LOGE(IMU_TAG, "MPU6050 not detected! Check I2C wiring.");
        vTaskDelete(NULL);
        return;
    }
    mpu6050_calibrate(200);
    last_time_us = esp_timer_get_time();

    int seq = 0;
    int64_t last_print_us = 0;
    while (true) {
        float ax, ay, az, gx, gy, gz;
        if (!mpu6050_read(&ax, &ay, &az, &gx, &gy, &gz)) {
            vTaskDelay(pdMS_TO_TICKS(CONTROL_PERIOD_MS));
            continue;
        }

        int64_t now = esp_timer_get_time();
        float dt = (float)(now - last_time_us) / 1000000.0f;
        last_time_us = now;

        if (dt > 0 && dt < 1.0f) {
            attitude_update(ax, ay, az, gx, gy, gz, dt);
        }

        seq++;
        if ((now - last_print_us) < (IMU_PRINT_PERIOD_MS * 1000)) {
            vTaskDelay(pdMS_TO_TICKS(CONTROL_PERIOD_MS));
            continue;
        }
        last_print_us = now;

        char buf[64];
        int len = snprintf(buf, sizeof(buf), "IMU,%d,%.2f,%.2f,%.2f\n",
                           seq, pitch, roll, yaw);
        uart_write_bytes(UART_PORT_NUM, buf, len);

        ESP_LOGI(IMU_TAG, "IMU,%d,%.2f,%.2f,%.2f | raw:ax=%.2f ay=%.2f az=%.2f gx=%.1f gy=%.1f gz=%.1f",
                 seq, pitch, roll, yaw, ax, ay, az, gx, gy, gz);

        vTaskDelay(pdMS_TO_TICKS(CONTROL_PERIOD_MS));
    }
}

static esp_err_t index_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, INDEX_HTML, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t jpg_handler(httpd_req_t *req)
{
    int64_t start_us = esp_timer_get_time();
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == NULL) {
        ESP_LOGE(TAG, "Camera capture failed");
        return httpd_resp_send_500(req);
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);

    ESP_LOGI(TAG, "jpg %ux%u %u bytes %" PRId64 "ms",
             fb->width, fb->height, fb->len, (esp_timer_get_time() - start_us) / 1000);
    esp_camera_fb_return(fb);
    return res;
}

static esp_err_t stream_handler(httpd_req_t *req)
{
    static const char *boundary = "\r\n--frame\r\n";
    char part_buf[96];

    esp_err_t res = httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
    if (res != ESP_OK) {
        return res;
    }

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb == NULL) {
            ESP_LOGE(TAG, "Camera capture failed");
            return ESP_FAIL;
        }

        size_t header_len = snprintf(part_buf, sizeof(part_buf),
                                     "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
                                     fb->len);
        res = httpd_resp_send_chunk(req, boundary, strlen(boundary));
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req, part_buf, header_len);
        }
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
        }
        esp_camera_fb_return(fb);

        if (res != ESP_OK) {
            ESP_LOGI(TAG, "Stream client disconnected");
            break;
        }

        vTaskDelay(pdMS_TO_TICKS(80));
    }

    return res;
}

static void start_wifi_ap(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = {
        .ap = {
            .ssid = WIFI_AP_SSID,
            .ssid_len = strlen(WIFI_AP_SSID),
            .channel = WIFI_AP_CHANNEL,
            .password = WIFI_AP_PASSWORD,
            .max_connection = WIFI_AP_MAX_CONN,
            .authmode = WIFI_AUTH_WPA_WPA2_PSK,
            .pmf_cfg = {
                .required = false,
            },
        },
    };

    if (strlen(WIFI_AP_PASSWORD) == 0) {
        wifi_config.ap.authmode = WIFI_AUTH_OPEN;
    }

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Wi-Fi AP started: ssid=%s password=%s url=http://192.168.4.1/",
             WIFI_AP_SSID, WIFI_AP_PASSWORD);
}

static void start_camera_server(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.ctrl_port = 32768;
    config.stack_size = 8192;

    httpd_handle_t server = NULL;
    ESP_ERROR_CHECK(httpd_start(&server, &config));

    httpd_uri_t index_uri = {
        .uri = "/",
        .method = HTTP_GET,
        .handler = index_handler,
    };
    httpd_uri_t jpg_uri = {
        .uri = "/jpg",
        .method = HTTP_GET,
        .handler = jpg_handler,
    };
    httpd_uri_t stream_uri = {
        .uri = "/stream",
        .method = HTTP_GET,
        .handler = stream_handler,
    };

    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &index_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &jpg_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &stream_uri));
    ESP_LOGI(TAG, "HTTP camera server started");
}

void app_main(void)
{
    esp_err_t nvs_ret = nvs_flash_init();
    if (nvs_ret == ESP_ERR_NVS_NO_FREE_PAGES || nvs_ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    } else {
        ESP_ERROR_CHECK(nvs_ret);
    }

    ESP_LOGI(TAG, "ESP32-S3 camera + IMU + UART web server starting");
    ESP_LOGI(TAG, "Camera pins: xclk=%d pclk=%d vsync=%d href=%d siod=%d sioc=%d",
             CAM_PIN_XCLK, CAM_PIN_PCLK, CAM_PIN_VSYNC, CAM_PIN_HREF,
             CAM_PIN_SIOD, CAM_PIN_SIOC);

    esp_err_t err = esp_camera_init(&camera_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_camera_init failed: 0x%x", err);
        ESP_LOGE(TAG, "Check PSRAM, camera ribbon cable, and pin mapping.");
        return;
    }

    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor != NULL) {
        ESP_LOGI(TAG, "sensor PID=0x%02x VER=0x%02x MIDL=0x%02x MIDH=0x%02x",
                 sensor->id.PID, sensor->id.VER, sensor->id.MIDL, sensor->id.MIDH);
    }

    ESP_LOGI(TAG, "Camera initialized");
    start_wifi_ap();
    start_camera_server();

    uart_init();
    i2c_master_init();
    if (mpu6050_attach_device()) {
        xTaskCreate(imu_task, "imu_task", 4096, NULL, 5, NULL);
    }

    while (true) {
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}
