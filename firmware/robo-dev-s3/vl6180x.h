#ifndef __VL6180X_H__
#define __VL6180X_H__

#include <cstdint>

#include <driver/i2c_master.h>
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

// ST VL6180X proximity / ranging sensor (I2C 0x29, 16-bit register addresses, range about 0-100 mm,
// up to ~200 mm on bright targets). Register sequence follows ST application note AN4545.
class Vl6180x {
public:
    static constexpr uint8_t kDefaultAddress = 0x29;
    static constexpr int kOutOfRange = -1;
    static constexpr int kMaxRangeMm = 200;  // readings of 200 or more are treated as "nothing there"

    bool Init(i2c_master_bus_handle_t bus, uint8_t addr = kDefaultAddress) {
        if (i2c_master_probe(bus, addr, 100) != ESP_OK) {
            ESP_LOGW(TAG, "No device at 0x%02X", addr);
            return false;
        }
        i2c_device_config_t cfg = {};
        cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
        cfg.device_address = addr;
        cfg.scl_speed_hz = 100 * 1000;
        if (i2c_master_bus_add_device(bus, &cfg, &dev_) != ESP_OK) {
            return false;
        }

        uint8_t id = 0;
        if (!Read8(kIdModel, &id) || id != 0xB4) {
            ESP_LOGW(TAG, "Unexpected model id 0x%02X (VL6180X is 0xB4)", id);
            return false;
        }
        uint8_t fresh = 0;
        if (!Read8(kFreshOutOfReset, &fresh)) {
            return false;
        }
        if (fresh == 1 && !LoadMandatorySettings()) {
            ESP_LOGW(TAG, "Sensor init failed");
            return false;
        }
        if (!LoadPublicSettings()) {
            ESP_LOGW(TAG, "Sensor settings failed");
            return false;
        }
        ready_ = true;
        ESP_LOGI(TAG, "VL6180X ready");
        return true;
    }

    bool ready() const { return ready_; }

    // Returns the distance in millimetres, or kOutOfRange on error / no target in range.
    int ReadRangeMm() {
        if (!ready_) {
            return kOutOfRange;
        }
        // Wait until the device can take a new measurement
        uint8_t status = 0;
        for (int i = 0; i < 20; i++) {
            if (Read8(kRangeStatus, &status) && (status & 0x01)) {
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(2));
        }
        if (!Write8(kRangeStart, 0x01)) {  // single shot
            return kOutOfRange;
        }
        uint8_t irq = 0;
        bool done = false;
        for (int i = 0; i < 40; i++) {  // 50 ms budget at 1 ms steps
            if (Read8(kIntStatus, &irq) && (irq & 0x07) == 0x04) {
                done = true;
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(2));
        }
        uint8_t range = 255, result_status = 0;
        if (done) {
            Read8(kRangeVal, &range);
            Read8(kRangeStatus, &result_status);
        }
        Write8(kIntClear, 0x07);
        if (!done || (result_status >> 4) != 0 || range >= kMaxRangeMm) {
            return kOutOfRange;
        }
        return range;
    }

private:
    static constexpr const char* TAG = "Vl6180x";

    static constexpr uint16_t kIdModel = 0x000;
    static constexpr uint16_t kFreshOutOfReset = 0x016;
    static constexpr uint16_t kIntClear = 0x015;
    static constexpr uint16_t kRangeStart = 0x018;
    static constexpr uint16_t kRangeStatus = 0x04D;
    static constexpr uint16_t kIntStatus = 0x04F;
    static constexpr uint16_t kRangeVal = 0x062;

    i2c_master_dev_handle_t dev_ = nullptr;
    bool ready_ = false;

    bool Read8(uint16_t reg, uint8_t* value) {
        uint8_t addr[2] = {(uint8_t)(reg >> 8), (uint8_t)reg};
        return i2c_master_transmit_receive(dev_, addr, 2, value, 1, 100) == ESP_OK;
    }

    bool Write8(uint16_t reg, uint8_t value) {
        uint8_t buf[3] = {(uint8_t)(reg >> 8), (uint8_t)reg, value};
        return i2c_master_transmit(dev_, buf, 3, 100) == ESP_OK;
    }

    bool LoadMandatorySettings() {
        static const struct { uint16_t reg; uint8_t value; } kSettings[] = {
            {0x0207, 0x01}, {0x0208, 0x01}, {0x0096, 0x00}, {0x0097, 0xFD}, {0x00E3, 0x01},
            {0x00E4, 0x03}, {0x00E5, 0x02}, {0x00E6, 0x01}, {0x00E7, 0x03}, {0x00F5, 0x02},
            {0x00D9, 0x05}, {0x00DB, 0xCE}, {0x00DC, 0x03}, {0x00DD, 0xF8}, {0x009F, 0x00},
            {0x00A3, 0x3C}, {0x00B7, 0x00}, {0x00BB, 0x3C}, {0x00B2, 0x09}, {0x00CA, 0x09},
            {0x0198, 0x01}, {0x01B0, 0x17}, {0x01AD, 0x00}, {0x00FF, 0x05}, {0x0100, 0x05},
            {0x0199, 0x05}, {0x01A6, 0x1B}, {0x01AC, 0x3E}, {0x01A7, 0x1F}, {0x0030, 0x00},
        };
        for (const auto& s : kSettings) {
            if (!Write8(s.reg, s.value)) {
                return false;
            }
        }
        return Write8(kFreshOutOfReset, 0x00);
    }

    bool LoadPublicSettings() {
        static const struct { uint16_t reg; uint8_t value; } kSettings[] = {
            {0x0011, 0x10},  // GPIO1 as active-high interrupt output
            {0x010A, 0x30},  // averaging sample period
            {0x003F, 0x46},  // light and dark gain
            {0x0031, 0xFF},  // auto calibration period
            {0x0040, 0x63},  // ALS integration time
            {0x002E, 0x01},  // temperature calibration
            {0x001B, 0x09},  // inter-measurement period (not used in single shot)
            {0x003E, 0x31},
            {0x0014, 0x24},  // interrupt when a range sample is ready
        };
        for (const auto& s : kSettings) {
            if (!Write8(s.reg, s.value)) {
                return false;
            }
        }
        return true;
    }
};

#endif  // __VL6180X_H__
