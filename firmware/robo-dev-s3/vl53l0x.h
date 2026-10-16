#ifndef __VL53L0X_H__
#define __VL53L0X_H__

#include <driver/i2c_master.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

// Minimal VL53L0X time-of-flight driver (single-shot ranging, default timing budget).
// The init sequence follows ST's reference tuning, as in Pololu's VL53L0X library.
// Unlike I2cDevice, every call returns an error instead of aborting, so a missing or
// unplugged sensor never reboots the robot.
class Vl53l0x {
public:
    static constexpr uint8_t kDefaultAddress = 0x29;
    static constexpr int kOutOfRange = -1;

    bool Init(i2c_master_bus_handle_t bus, uint8_t addr = kDefaultAddress) {
        if (i2c_master_probe(bus, addr, 100) != ESP_OK) {
            ESP_LOGW(TAG, "No device at 0x%02X", addr);
            return false;
        }
        i2c_device_config_t cfg = {};
        cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
        cfg.device_address = addr;
        cfg.scl_speed_hz = 400 * 1000;
        if (i2c_master_bus_add_device(bus, &cfg, &dev_) != ESP_OK) {
            return false;
        }

        uint8_t id = 0;
        if (!Read8(0xC0, &id) || id != 0xEE) {
            ESP_LOGW(TAG, "Unexpected model id 0x%02X", id);
            return false;
        }
        if (!InitSensor()) {
            ESP_LOGW(TAG, "Sensor init failed");
            return false;
        }
        ready_ = true;
        ESP_LOGI(TAG, "VL53L0X ready");
        return true;
    }

    bool ready() const { return ready_; }

    // Returns the distance in millimetres, or kOutOfRange on timeout / no target.
    int ReadRangeMm() {
        if (!ready_) {
            return kOutOfRange;
        }
        bool ok = Write8(0x80, 0x01) && Write8(0xFF, 0x01) && Write8(0x00, 0x00) &&
                  Write8(0x91, stop_variable_) && Write8(0x00, 0x01) && Write8(0xFF, 0x00) &&
                  Write8(0x80, 0x00) && Write8(0x00, 0x01);
        if (!ok) {
            return kOutOfRange;
        }
        // Wait for the start bit to clear, then for the measurement to complete
        if (!WaitFor(0x00, 0x01, 0x00) || !WaitFor(0x13, 0x07, 0x00, true)) {
            return kOutOfRange;
        }
        uint16_t range = 0;
        bool read_ok = Read16(0x14 + 10, &range);
        Write8(0x0B, 0x01);  // clear interrupt
        if (!read_ok || range >= 8190) {
            return kOutOfRange;
        }
        return range;
    }

private:
    static constexpr const char* TAG = "Vl53l0x";

    i2c_master_dev_handle_t dev_ = nullptr;
    uint8_t stop_variable_ = 0;
    bool ready_ = false;

    bool Write8(uint8_t reg, uint8_t value) {
        uint8_t buf[2] = {reg, value};
        return i2c_master_transmit(dev_, buf, 2, 100) == ESP_OK;
    }

    bool Write16(uint8_t reg, uint16_t value) {
        uint8_t buf[3] = {reg, (uint8_t)(value >> 8), (uint8_t)value};
        return i2c_master_transmit(dev_, buf, 3, 100) == ESP_OK;
    }

    bool WriteMulti(uint8_t reg, const uint8_t* data, size_t len) {
        uint8_t buf[8];
        if (len + 1 > sizeof(buf)) {
            return false;
        }
        buf[0] = reg;
        for (size_t i = 0; i < len; i++) {
            buf[i + 1] = data[i];
        }
        return i2c_master_transmit(dev_, buf, len + 1, 100) == ESP_OK;
    }

    bool Read8(uint8_t reg, uint8_t* value) {
        return i2c_master_transmit_receive(dev_, &reg, 1, value, 1, 100) == ESP_OK;
    }

    bool Read16(uint8_t reg, uint16_t* value) {
        uint8_t buf[2];
        if (i2c_master_transmit_receive(dev_, &reg, 1, buf, 2, 100) != ESP_OK) {
            return false;
        }
        *value = ((uint16_t)buf[0] << 8) | buf[1];
        return true;
    }

    bool ReadMulti(uint8_t reg, uint8_t* data, size_t len) {
        return i2c_master_transmit_receive(dev_, &reg, 1, data, len, 100) == ESP_OK;
    }

    bool UpdateBits(uint8_t reg, uint8_t clear_mask, uint8_t set_mask) {
        uint8_t v;
        return Read8(reg, &v) && Write8(reg, (v & ~clear_mask) | set_mask);
    }

    // Polls until (reg & mask) == value, or (reg & mask) != value when `not_equal` is set.
    bool WaitFor(uint8_t reg, uint8_t mask, uint8_t value, bool not_equal = false,
                 int timeout_ms = 500) {
        int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
        while (esp_timer_get_time() < deadline) {
            uint8_t v;
            if (!Read8(reg, &v)) {
                return false;
            }
            if (not_equal ? ((v & mask) != value) : ((v & mask) == value)) {
                return true;
            }
            vTaskDelay(pdMS_TO_TICKS(1));
        }
        return false;
    }

    bool GetSpadInfo(uint8_t* count, bool* is_aperture) {
        bool ok = Write8(0x80, 0x01) && Write8(0xFF, 0x01) && Write8(0x00, 0x00) &&
                  Write8(0xFF, 0x06) && UpdateBits(0x83, 0, 0x04) && Write8(0xFF, 0x07) &&
                  Write8(0x81, 0x01) && Write8(0x80, 0x01) && Write8(0x94, 0x6B) &&
                  Write8(0x83, 0x00);
        if (!ok || !WaitFor(0x83, 0xFF, 0x00, true)) {
            return false;
        }
        uint8_t tmp;
        ok = Write8(0x83, 0x01) && Read8(0x92, &tmp) && Write8(0x81, 0x00) &&
             Write8(0xFF, 0x06) && UpdateBits(0x83, 0x04, 0) && Write8(0xFF, 0x01) &&
             Write8(0x00, 0x01) && Write8(0xFF, 0x00) && Write8(0x80, 0x00);
        if (!ok) {
            return false;
        }
        *count = tmp & 0x7F;
        *is_aperture = (tmp >> 7) & 0x01;
        return true;
    }

    bool SingleRefCalibration(uint8_t vhv_init_byte) {
        if (!Write8(0x00, 0x01 | vhv_init_byte) || !WaitFor(0x13, 0x07, 0x00, true)) {
            return false;
        }
        return Write8(0x0B, 0x01) && Write8(0x00, 0x00);
    }

    bool InitSensor() {
        // Use 2.8 V I/O mode and I2C standard mode
        if (!UpdateBits(0x89, 0, 0x01) || !Write8(0x88, 0x00)) {
            return false;
        }

        // Read the stop variable needed before every single-shot measurement
        bool ok = Write8(0x80, 0x01) && Write8(0xFF, 0x01) && Write8(0x00, 0x00) &&
                  Read8(0x91, &stop_variable_) && Write8(0x00, 0x01) && Write8(0xFF, 0x00) &&
                  Write8(0x80, 0x00);
        if (!ok) {
            return false;
        }

        // Disable SIGNAL_RATE_MSRC and SIGNAL_RATE_PRE_RANGE limit checks, set limit to 0.25 MCPS
        if (!UpdateBits(0x60, 0, 0x12) || !Write16(0x44, 32) || !Write8(0x01, 0xFF)) {
            return false;
        }

        // Reference SPAD setup
        uint8_t spad_count;
        bool spad_is_aperture;
        if (!GetSpadInfo(&spad_count, &spad_is_aperture)) {
            return false;
        }
        uint8_t ref_spad_map[6];
        if (!ReadMulti(0xB0, ref_spad_map, 6)) {
            return false;
        }
        if (!Write8(0xFF, 0x01) || !Write8(0x4F, 0x00) || !Write8(0x4E, 0x2C) ||
            !Write8(0xFF, 0x00) || !Write8(0xB6, 0xB4)) {
            return false;
        }
        uint8_t first_spad = spad_is_aperture ? 12 : 0;
        uint8_t enabled = 0;
        for (uint8_t i = 0; i < 48; i++) {
            if (i < first_spad || enabled == spad_count) {
                ref_spad_map[i / 8] &= ~(1 << (i % 8));
            } else if ((ref_spad_map[i / 8] >> (i % 8)) & 0x01) {
                enabled++;
            }
        }
        if (!WriteMulti(0xB0, ref_spad_map, 6)) {
            return false;
        }

        if (!LoadTuningSettings()) {
            return false;
        }

        // GPIO: new-sample-ready interrupt, active low
        if (!Write8(0x0A, 0x04) || !UpdateBits(0x84, 0x10, 0) || !Write8(0x0B, 0x01)) {
            return false;
        }

        // Calibration
        if (!Write8(0x01, 0xE8)) {
            return false;
        }
        if (!Write8(0x01, 0x01) || !SingleRefCalibration(0x40)) {
            return false;
        }
        if (!Write8(0x01, 0x02) || !SingleRefCalibration(0x00)) {
            return false;
        }
        return Write8(0x01, 0xE8);
    }

    bool LoadTuningSettings() {
        static const uint8_t settings[][2] = {
            {0xFF, 0x01}, {0x00, 0x00}, {0xFF, 0x00}, {0x09, 0x00}, {0x10, 0x00}, {0x11, 0x00},
            {0x24, 0x01}, {0x25, 0xFF}, {0x75, 0x00}, {0xFF, 0x01}, {0x4E, 0x2C}, {0x48, 0x00},
            {0x30, 0x20}, {0xFF, 0x00}, {0x30, 0x09}, {0x54, 0x00}, {0x31, 0x04}, {0x32, 0x03},
            {0x40, 0x83}, {0x46, 0x25}, {0x60, 0x00}, {0x27, 0x00}, {0x50, 0x06}, {0x51, 0x00},
            {0x52, 0x96}, {0x56, 0x08}, {0x57, 0x30}, {0x61, 0x00}, {0x62, 0x00}, {0x64, 0x00},
            {0x65, 0x00}, {0x66, 0xA0}, {0xFF, 0x01}, {0x22, 0x32}, {0x47, 0x14}, {0x49, 0xFF},
            {0x4A, 0x00}, {0xFF, 0x00}, {0x7A, 0x0A}, {0x7B, 0x00}, {0x78, 0x21}, {0xFF, 0x01},
            {0x23, 0x34}, {0x42, 0x00}, {0x44, 0xFF}, {0x45, 0x26}, {0x46, 0x05}, {0x40, 0x40},
            {0x0E, 0x06}, {0x20, 0x1A}, {0x43, 0x40}, {0xFF, 0x00}, {0x34, 0x03}, {0x35, 0x44},
            {0xFF, 0x01}, {0x31, 0x04}, {0x4B, 0x09}, {0x4C, 0x05}, {0x4D, 0x04}, {0xFF, 0x00},
            {0x44, 0x00}, {0x45, 0x20}, {0x47, 0x08}, {0x48, 0x28}, {0x67, 0x00}, {0x70, 0x04},
            {0x71, 0x01}, {0x72, 0xFE}, {0x76, 0x00}, {0x77, 0x00}, {0xFF, 0x01}, {0x0D, 0x01},
            {0xFF, 0x00}, {0x80, 0x01}, {0x01, 0xF8}, {0xFF, 0x01}, {0x8E, 0x01}, {0x00, 0x01},
            {0xFF, 0x00}, {0x80, 0x00},
        };
        for (const auto& s : settings) {
            if (!Write8(s[0], s[1])) {
                return false;
            }
        }
        return true;
    }
};

#endif // __VL53L0X_H__
