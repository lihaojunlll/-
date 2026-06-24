#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_camera.h"
#include "esp_err.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "img_converters.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "camera";

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
    esp_err_t res;
    uint8_t *jpg_buf = NULL;
    size_t jpg_len = 0;

    if (fb->format == PIXFORMAT_JPEG) {
        res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
        jpg_len = fb->len;
    } else if (frame2jpg(fb, 80, &jpg_buf, &jpg_len)) {
        res = httpd_resp_send(req, (const char *)jpg_buf, jpg_len);
        free(jpg_buf);
    } else {
        ESP_LOGE(TAG, "JPEG conversion failed");
        res = httpd_resp_send_500(req);
    }

    ESP_LOGI(TAG, "jpg %ux%u %u bytes %" PRId64 "ms",
             fb->width, fb->height, jpg_len,
             (esp_timer_get_time() - start_us) / 1000);
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

        uint8_t *jpg_buf = NULL;
        size_t jpg_len = fb->len;
        const uint8_t *jpg_data = fb->buf;
        if (fb->format != PIXFORMAT_JPEG) {
            if (!frame2jpg(fb, 80, &jpg_buf, &jpg_len)) {
                ESP_LOGE(TAG, "JPEG conversion failed");
                esp_camera_fb_return(fb);
                return ESP_FAIL;
            }
            jpg_data = jpg_buf;
        }

        size_t header_len = snprintf(part_buf, sizeof(part_buf),
                                     "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
                                     jpg_len);
        res = httpd_resp_send_chunk(req, boundary, strlen(boundary));
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req, part_buf, header_len);
        }
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req, (const char *)jpg_data, jpg_len);
        }
        if (jpg_buf != NULL) {
            free(jpg_buf);
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

void camera_web_init(camera_config_t *config)
{
    esp_err_t err = esp_camera_init(config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_camera_init failed: 0x%x", err);
        return;
    }

    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor != NULL) {
        ESP_LOGI(TAG, "sensor PID=0x%02x VER=0x%02x MIDL=0x%02x MIDH=0x%02x",
                 sensor->id.PID, sensor->id.VER, sensor->id.MIDL, sensor->id.MIDH);
    }
    ESP_LOGI(TAG, "Camera initialized");

    httpd_config_t http_cfg = HTTPD_DEFAULT_CONFIG();
    http_cfg.server_port = 80;
    http_cfg.ctrl_port = 32768;
    http_cfg.stack_size = 8192;

    httpd_handle_t server = NULL;
    ESP_ERROR_CHECK(httpd_start(&server, &http_cfg));

    httpd_uri_t index_uri = { .uri = "/", .method = HTTP_GET, .handler = index_handler };
    httpd_uri_t jpg_uri   = { .uri = "/jpg", .method = HTTP_GET, .handler = jpg_handler };
    httpd_uri_t stream_uri = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler };

    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &index_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &jpg_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &stream_uri));
    ESP_LOGI(TAG, "HTTP camera server started");
}
