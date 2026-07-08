#include <math.h>
#include <stdint.h>
#include "esp_camera.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "app_config.h"
#include "camera_vision.h"
#include "uart/uart_link.h"

static const char *TAG = "vision";

static camera_vision_state_t s_vision_state;
static portMUX_TYPE s_vision_state_lock = portMUX_INITIALIZER_UNLOCKED;

typedef struct {
    float center;
    float quality;
    int black_count;
    int sample_count;
} roi_result_t;

typedef struct {
    int turn;
    float slowdown;
    float quality;
} route_hint_t;

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

static uint8_t pixel_luma(camera_fb_t *fb, int x, int y)
{
    if (fb->format == PIXFORMAT_GRAYSCALE) {
        return fb->buf[y * fb->width + x];
    }

    if (fb->format == PIXFORMAT_RGB565) {
        const uint8_t *px = fb->buf + (y * fb->width + x) * 2;
        return rgb565_luma(px);
    }

    return 255;
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
        for (int x = 0; x < width; x += VISION_SAMPLE_STEP_X) {
            uint8_t lum = pixel_luma(fb, x, y);
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

static float clamp_unit(float value)
{
    if (value > 1.0f) return 1.0f;
    if (value < -1.0f) return -1.0f;
    return value;
}

static float clamp_01(float value)
{
    if (value > 1.0f) return 1.0f;
    if (value < 0.0f) return 0.0f;
    return value;
}

static route_hint_t classify_route(roi_result_t near_roi,
                                   roi_result_t mid_roi,
                                   roi_result_t far_roi,
                                   roi_result_t look_roi)
{
    float quality = near_roi.quality;
    if (mid_roi.quality < quality) quality = mid_roi.quality;
    if (far_roi.quality < quality) quality = far_roi.quality;

    route_hint_t hint = {
        .turn = 0,
        .slowdown = 0.0f,
        .quality = quality,
    };

    if (quality < VISION_TURN_MIN_QUALITY) {
        return hint;
    }

    float look_center = far_roi.center;
    if (look_roi.quality >= VISION_TURN_MIN_QUALITY) {
        look_center = look_roi.center;
    }

    float target_score = near_roi.center * 0.10f +
                         mid_roi.center * 0.20f +
                         far_roi.center * 0.30f +
                         look_center * 0.40f;
    float curve_score = (far_roi.center - near_roi.center) * 0.45f +
                        (look_center - near_roi.center) * 0.35f;
    float turn_score = clamp_unit(target_score * 0.65f + curve_score * 0.35f);

    float abs_score = fabsf(turn_score);
    if (abs_score >= VISION_TURN_THRESHOLD) {
        hint.turn = turn_score > 0.0f ? 1 : -1;
    }

    float ahead_score = fabsf(target_score);
    float curve_abs = fabsf(curve_score);
    if (curve_abs > ahead_score) {
        ahead_score = curve_abs;
    }
    float bend_deadband = 0.05f;
    hint.slowdown = clamp_01((ahead_score - bend_deadband) /
                             (VISION_FULL_SLOWDOWN - bend_deadband));
    return hint;
}

void camera_vision_get_state(camera_vision_state_t *out)
{
    if (out == NULL) {
        return;
    }
    portENTER_CRITICAL(&s_vision_state_lock);
    *out = s_vision_state;
    portEXIT_CRITICAL(&s_vision_state_lock);
}

static void camera_vision_set_state(int seq,
                                    int frame_width,
                                    int frame_height,
                                    int near_y,
                                    int mid_y,
                                    int far_y,
                                    int look_y,
                                    roi_result_t near_roi,
                                    roi_result_t mid_roi,
                                    roi_result_t far_roi,
                                    roi_result_t look_roi,
                                    int fit_count,
                                    const int *fit_y,
                                    const roi_result_t *fit_roi,
                                    float curve,
                                    float quality,
                                    route_hint_t route)
{
    camera_vision_state_t state = {
        .seq = seq,
        .frame_width = frame_width,
        .frame_height = frame_height,
        .near_x = near_roi.center,
        .mid_x = mid_roi.center,
        .far_x = far_roi.center,
        .look_x = look_roi.center,
        .near_y = near_y,
        .mid_y = mid_y,
        .far_y = far_y,
        .look_y = look_y,
        .curve = curve,
        .quality = quality,
        .turn = route.turn,
        .slowdown = route.slowdown,
        .near_black = near_roi.black_count,
        .near_samples = near_roi.sample_count,
        .mid_black = mid_roi.black_count,
        .mid_samples = mid_roi.sample_count,
        .far_black = far_roi.black_count,
        .far_samples = far_roi.sample_count,
        .look_black = look_roi.black_count,
        .look_samples = look_roi.sample_count,
        .fit_count = fit_count,
        .update_us = esp_timer_get_time(),
    };

    for (int i = 0; i < fit_count && i < CAMERA_VISION_FIT_POINTS; i++) {
        state.fit_x[i] = fit_roi[i].center;
        state.fit_y[i] = fit_y[i];
        state.fit_quality[i] = fit_roi[i].quality;
    }

    portENTER_CRITICAL(&s_vision_state_lock);
    s_vision_state = state;
    portEXIT_CRITICAL(&s_vision_state_lock);
}

void camera_vision_task(void *arg)
{
    int seq = 0;
    int64_t last_log_us = 0;
    vTaskDelay(pdMS_TO_TICKS(1000));

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb == NULL) {
            ESP_LOGE(TAG, "Camera capture failed");
            vTaskDelay(pdMS_TO_TICKS(VISION_PERIOD_MS));
            continue;
        }

        if (fb->format != PIXFORMAT_GRAYSCALE && fb->format != PIXFORMAT_RGB565) {
            ESP_LOGW(TAG, "Unsupported pixel format for vision: %d", fb->format);
            esp_camera_fb_return(fb);
            vTaskDelay(pdMS_TO_TICKS(VISION_PERIOD_MS));
            continue;
        }

        int frame_width = fb->width;
        int frame_height = fb->height;
        int near_y = (frame_height * VISION_NEAR_ROW_NUM) / VISION_NEAR_ROW_DEN;
        int mid_y = (frame_height * VISION_MID_ROW_NUM) / VISION_MID_ROW_DEN;
        int far_y = (frame_height * VISION_FAR_ROW_NUM) / VISION_FAR_ROW_DEN;
        int look_y = (frame_height * VISION_LOOK_ROW_NUM) / VISION_LOOK_ROW_DEN;
        roi_result_t near_roi = analyze_roi(fb, near_y);
        roi_result_t mid_roi = analyze_roi(fb, mid_y);
        roi_result_t far_roi = analyze_roi(fb, far_y);
        roi_result_t look_roi = analyze_roi(fb, look_y);

        int fit_y[CAMERA_VISION_FIT_POINTS];
        roi_result_t fit_roi[CAMERA_VISION_FIT_POINTS];
        int fit_top_y = look_y;
        int fit_bottom_y = near_y;
        for (int i = 0; i < CAMERA_VISION_FIT_POINTS; i++) {
            int y = fit_top_y;
            if (CAMERA_VISION_FIT_POINTS > 1) {
                y = fit_top_y + ((fit_bottom_y - fit_top_y) * i) / (CAMERA_VISION_FIT_POINTS - 1);
            }
            fit_y[i] = y;
            fit_roi[i] = analyze_roi(fb, y);
        }
        esp_camera_fb_return(fb);

        float quality = near_roi.quality;
        if (far_roi.quality < quality) quality = far_roi.quality;
        route_hint_t route = classify_route(near_roi, mid_roi, far_roi, look_roi);

        float curve = 0.0f;
        if (quality > 0.0f) {
            curve = far_roi.center - near_roi.center;
            curve = clamp_unit(curve);
        }

        seq++;
        camera_vision_set_state(seq, frame_width, frame_height,
                                near_y, mid_y, far_y, look_y,
                                near_roi, mid_roi, far_roi, look_roi,
                                CAMERA_VISION_FIT_POINTS, fit_y, fit_roi,
                                curve, quality, route);
        uart_link_send_camera(seq, near_roi.center, far_roi.center, curve,
                              quality, route.turn, route.slowdown);

        int64_t now_us = esp_timer_get_time();
        if (now_us - last_log_us >= (int64_t)VISION_LOG_PERIOD_MS * 1000) {
            ESP_LOGI(TAG, "CAM,%d,near=%.2f mid=%.2f far=%.2f look=%.2f curve=%.2f quality=%.2f turn=%d slow=%.2f black=%d/%d %d/%d %d/%d %d/%d",
                     seq, near_roi.center, mid_roi.center, far_roi.center,
                     look_roi.center, curve, quality,
                     route.turn, route.slowdown,
                     near_roi.black_count, near_roi.sample_count,
                     mid_roi.black_count, mid_roi.sample_count,
                     far_roi.black_count, far_roi.sample_count,
                     look_roi.black_count, look_roi.sample_count);
            last_log_us = now_us;
        }

        vTaskDelay(pdMS_TO_TICKS(VISION_PERIOD_MS));
    }
}
