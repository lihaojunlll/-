#pragma once

#include <stdint.h>

#define CAMERA_VISION_FIT_POINTS 13

typedef struct {
    int seq;
    int frame_width;
    int frame_height;
    float near_x;
    float mid_x;
    float far_x;
    float look_x;
    int near_y;
    int mid_y;
    int far_y;
    int look_y;
    float curve;
    float quality;
    int turn;
    float slowdown;
    int near_black;
    int near_samples;
    int mid_black;
    int mid_samples;
    int far_black;
    int far_samples;
    int look_black;
    int look_samples;
    int fit_count;
    float fit_x[CAMERA_VISION_FIT_POINTS];
    int fit_y[CAMERA_VISION_FIT_POINTS];
    float fit_quality[CAMERA_VISION_FIT_POINTS];
    int64_t update_us;
} camera_vision_state_t;

void camera_vision_task(void *arg);
void camera_vision_get_state(camera_vision_state_t *out);
