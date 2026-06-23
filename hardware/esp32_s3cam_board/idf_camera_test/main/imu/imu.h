#pragma once
#include <stdbool.h>
#include "driver/i2c_master.h"

typedef struct {
    float pitch, roll, yaw;
    float ax, ay, az;
    float gx, gy, gz;
    int seq;
} imu_sample_t;

bool imu_attach(i2c_master_bus_handle_t bus);
void imu_task(void *arg);
bool imu_get_latest(imu_sample_t *out);
