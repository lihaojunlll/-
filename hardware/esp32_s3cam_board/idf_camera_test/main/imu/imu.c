#include <math.h>
#include <string.h>
#include "driver/i2c_master.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "app_config.h"
#include "imu/imu.h"
#include "uart/uart_link.h"

static const char *TAG = "imu";

static i2c_master_dev_handle_t i2c_dev;
static uint8_t mpu6050_addr;

static float ax_off, ay_off, az_off;
static float gx_off, gy_off, gz_off;
static float az_scale = 1.0f;

static float pitch, roll, yaw;
static int64_t last_time_us;

static imu_sample_t latest_sample;
static SemaphoreHandle_t sample_mutex;

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

static void mpu6050_write_reg(uint8_t reg, uint8_t val)
{
    esp_err_t ret = i2c_write_reg(reg, val);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C write reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
    }
}

static esp_err_t mpu6050_read_regs(uint8_t reg, uint8_t *data, size_t len)
{
    esp_err_t ret = i2c_read_regs(reg, data, len);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C read reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
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

static bool mpu6050_read_raw(float *ax, float *ay, float *az,
                              float *gx, float *gy, float *gz)
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

    ESP_LOGI(TAG, "Calibrated %d samples, offsets: ax=%.4f ay=%.4f az=%.4f gx=%.4f gy=%.4f gz=%.4f",
             samples, ax_off, ay_off, az_off, gx_off, gy_off, gz_off);
}

static bool mpu6050_read(float *ax, float *ay, float *az,
                          float *gx, float *gy, float *gz)
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

static float wrap_180(float angle)
{
    float r = fmodf(angle + 180.0f, 360.0f);
    if (r < 0) r += 360.0f;
    return r - 180.0f;
}

static void attitude_update(float ax, float ay, float az,
                             float gx, float gy, float gz, float dt)
{
    float acc_pitch = atan2f(-ax, sqrtf(ay * ay + az * az)) * 57.2958f;
    float acc_roll = atan2f(ay, az) * 57.2958f;

    pitch = ATTITUDE_ALPHA * (pitch + gx * dt) + (1.0f - ATTITUDE_ALPHA) * acc_pitch;
    roll  = ATTITUDE_ALPHA * (roll + gy * dt) + (1.0f - ATTITUDE_ALPHA) * acc_roll;
    yaw  += gz * dt;

    pitch = wrap_180(pitch);
    roll  = wrap_180(roll);
    yaw   = wrap_180(yaw);
}

bool imu_attach(i2c_master_bus_handle_t bus)
{
    const uint8_t candidates[] = {MPU6050_ADDR_LOW, MPU6050_ADDR_HIGH};

    for (size_t i = 0; i < sizeof(candidates); i++) {
        uint8_t addr = candidates[i];

        i2c_device_config_t dev_cfg = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address = addr,
            .scl_speed_hz = I2C_MASTER_FREQ_HZ,
        };

        esp_err_t ret = i2c_master_bus_add_device(bus, &dev_cfg, &i2c_dev);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Add I2C device 0x%02X failed: %s",
                     addr, esp_err_to_name(ret));
            continue;
        }

        vTaskDelay(pdMS_TO_TICKS(20));
        uint8_t who = 0;
        ret = i2c_read_regs(MPU6050_REG_WHO_AM_I, &who, 1);
        ESP_LOGI(TAG, "I2C read WHO_AM_I at 0x%02X: %s, value=0x%02X",
                 addr, esp_err_to_name(ret), who);

        if (ret == ESP_OK && who == 0x68) {
            mpu6050_addr = addr;
            ESP_LOGI(TAG, "MPU6050 attached at I2C address 0x%02X", mpu6050_addr);

            sample_mutex = xSemaphoreCreateMutex();
            return true;
        }

        ESP_ERROR_CHECK_WITHOUT_ABORT(i2c_master_bus_rm_device(i2c_dev));
        i2c_dev = NULL;
    }

    ESP_LOGE(TAG, "MPU6050 not found at 0x68 or 0x69.");
    return false;
}

bool imu_get_latest(imu_sample_t *out)
{
    if (sample_mutex == NULL || out == NULL) return false;
    if (xSemaphoreTake(sample_mutex, pdMS_TO_TICKS(10)) != pdTRUE) return false;

    *out = latest_sample;
    xSemaphoreGive(sample_mutex);
    return true;
}

void imu_task(void *arg)
{
    mpu6050_init_sensor();
    vTaskDelay(pdMS_TO_TICKS(300));

    uint8_t who = mpu6050_whoami();
    ESP_LOGI(TAG, "MPU6050 WHO_AM_I: 0x%02X (expected 0x68)", who);
    if (who != 0x68) {
        ESP_LOGE(TAG, "MPU6050 not detected! Check I2C wiring.");
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

        if (sample_mutex && xSemaphoreTake(sample_mutex, 0) == pdTRUE) {
            latest_sample = (imu_sample_t){
                .pitch = pitch, .roll = roll, .yaw = yaw,
                .ax = ax, .ay = ay, .az = az,
                .gx = gx, .gy = gy, .gz = gz,
                .seq = seq,
            };
            xSemaphoreGive(sample_mutex);
        }

        if ((now - last_print_us) >= (IMU_PRINT_PERIOD_MS * 1000)) {
            last_print_us = now;
            uart_link_send_imu(seq, pitch, roll, yaw);

            ESP_LOGI(TAG, "IMU,%d,%.2f,%.2f,%.2f | raw:ax=%.2f ay=%.2f az=%.2f gx=%.1f gy=%.1f gz=%.1f",
                     seq, pitch, roll, yaw, ax, ay, az, gx, gy, gz);
        }

        vTaskDelay(pdMS_TO_TICKS(CONTROL_PERIOD_MS));
    }
}
