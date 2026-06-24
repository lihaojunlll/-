#include <math.h>
#include <stdint.h>
#include "esp_camera.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "app_config.h"
#include "uart/uart_link.h"

static const char *TAG = "vision";

typedef struct {
    float center;
    float quality;
    int black_count;
    int sample_count;
} roi_result_t;

static uint8_t rgb565_luma(const uint8_t *p)
{
    uint16_t raw = (uint16_t)p[0] | ((uint16_t)p[1] << 8);
    uint8_t r = (raw >> 11) & 0x1F;
    uint8_t g = (raw >> 5) & 0x3F;
    uint8_t b = raw & 0x1F;

    uint16_t r8 = (r * 255) / 31;
    uint16_t g8 = (g * 255) / 63;
    uint16_t b8 = (b * 255) / 31;
    return (uint8_t)((30 * r8 + 59 * g8 + 11 * b8) / 100);
}

static roi_result_t analyze_roi(camera_fb_t *fb, int center_y)
{
    int width = fb->width;
    int height = fb->height;
    int y0 = center_y - VISION_ROI_HEIGHT / 2;
    int y1 = center_y + VISION_ROI_HEIGHT / 2;
    if (y0 < 0) y0 = 0;
    if (y1 > height) y1 = height;

    int black_count = 0;
    int sample_count = 0;
    int weighted_x = 0;

    for (int y = y0; y < y1; y += VISION_SAMPLE_STEP_Y) {
        const uint8_t *row = fb->buf + y * width * 2;
        for (int x = 0; x < width; x += VISION_SAMPLE_STEP_X) {
            const uint8_t *px = row + x * 2;
            uint8_t lum = rgb565_luma(px);
            sample_count++;
            if (lum < VISION_BLACK_Y_THRESHOLD) {
                black_count++;
                weighted_x += x;
            }
        }
    }

    roi_result_t result = {
        .center = 0.0f,
        .quality = 0.0f,
        .black_count = black_count,
        .sample_count = sample_count,
    };

    if (black_count <= 0 || sample_count <= 0) {
        return result;
    }

    float avg_x = (float)weighted_x / (float)black_count;
    result.center = (avg_x - (float)(width - 1) * 0.5f) / ((float)(width - 1) * 0.5f);
    if (result.center > 1.0f) result.center = 1.0f;
    if (result.center < -1.0f) result.center = -1.0f;

    float black_ratio = (float)black_count / (float)sample_count;
    result.quality = black_ratio / 0.18f;
    if (result.quality > 1.0f) result.quality = 1.0f;
    if (black_ratio > 0.45f) {
        result.quality *= 0.4f;
    }
    return result;
}

void camera_vision_task(void *arg)
{
    int seq = 0;
    vTaskDelay(pdMS_TO_TICKS(1000));

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb == NULL) {
            ESP_LOGE(TAG, "Camera capture failed");
            vTaskDelay(pdMS_TO_TICKS(VISION_PERIOD_MS));
            continue;
        }

        if (fb->format != PIXFORMAT_RGB565) {
            ESP_LOGW(TAG, "Unsupported pixel format for vision: %d", fb->format);
            esp_camera_fb_return(fb);
            vTaskDelay(pdMS_TO_TICKS(VISION_PERIOD_MS));
            continue;
        }

        int near_y = (fb->height * VISION_NEAR_ROW_NUM) / VISION_NEAR_ROW_DEN;
        int far_y = (fb->height * VISION_FAR_ROW_NUM) / VISION_FAR_ROW_DEN;
        roi_result_t near_roi = analyze_roi(fb, near_y);
        roi_result_t far_roi = analyze_roi(fb, far_y);
        esp_camera_fb_return(fb);

        float quality = near_roi.quality;
        if (far_roi.quality < quality) quality = far_roi.quality;

        float curve = 0.0f;
        if (quality > 0.0f) {
            curve = far_roi.center - near_roi.center;
            if (curve > 1.0f) curve = 1.0f;
            if (curve < -1.0f) curve = -1.0f;
        }

        seq++;
        uart_link_send_camera(seq, near_roi.center, far_roi.center, curve, quality);

        ESP_LOGI(TAG, "CAM,%d,near=%.2f far=%.2f curve=%.2f quality=%.2f black=%d/%d %d/%d",
                 seq, near_roi.center, far_roi.center, curve, quality,
                 near_roi.black_count, near_roi.sample_count,
                 far_roi.black_count, far_roi.sample_count);

        vTaskDelay(pdMS_TO_TICKS(VISION_PERIOD_MS));
    }
}
