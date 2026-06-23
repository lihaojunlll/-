#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "driver/ledc.h"
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

#define WIFI_AP_SSID      "S3CAM"
#define WIFI_AP_PASSWORD  "12345678"
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
    "<p>Connect to Wi-Fi: S3CAM / 12345678, then open http://192.168.4.1/</p>"
    "</div></body></html>";

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

    ESP_LOGI(TAG, "ESP32-S3 camera web server starting");
    ESP_LOGI(TAG, "pins: xclk=%d pclk=%d vsync=%d href=%d siod=%d sioc=%d",
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

    while (true) {
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}
