#ifndef __SERIAL_SETUP_H__
#define __SERIAL_SETUP_H__

#include <cstdio>
#include <functional>
#include <algorithm>
#include <string>
#include <vector>

#include <cJSON.h>
#include <driver/uart.h>
#include <driver/usb_serial_jtag.h>
#include <esp_app_desc.h>
#include <esp_chip_info.h>
#include <esp_flash.h>
#include <esp_log.h>
#include <esp_system.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <sdkconfig.h>

#include "application.h"
#include "board.h"
#include "codecs/no_audio_codec.h"
#include "alarm_chime.h"
#include "assets/lang_config.h"
#include "ssid_manager.h"
#include "robot_config.h"

// Lets Robo Dev (PC) set the board up over the console UART (COM port), so a board can be
// configured and tested right after flashing without joining its hotspot.
//
// Commands, one per line (replies are single lines starting with RD_):
//   RD_PING                          -> RD_PONG <firmware version>
//   RD_INFO                          -> RD_INFO {json: board, version, chip, flash_mb, sensor, ...}
//   RD_VOL [0-100]                   -> sets (optional) and reports the speaker volume, RD_VOL_OK <volume>
//   RD_TIME                          -> RD_TIME_OK <local time> valid=0|1 (valid once the clock is set)
//   RD_ALARM [ON|OFF|QUIET f t]      -> half-hourly chime: status, switch, quiet hours [f, t)
//   RD_ALARM_TEST [n]                -> plays chime piece n now (RD_ALARM_TEST_OK <name>)
//   RD_BEEP_ON / RD_BEEP_OFF     -> repeats the beep every second until switched off
//   RD_BEEP                       -> plays a short sound on the speaker, RD_BEEP_OK
//   RD_WIFI {"s":"ssid","p":"pass"}  -> saves the network, RD_WIFI_OK, then restarts
//   RD_WIFI_CLEAR                    -> forgets all saved networks, RD_WIFI_OK, then restarts
//   RD_CFG {json}                    -> validates and stores the config, RD_CFG_OK, then restarts
//                                        (RD_CFG_ERR <reason> when it is not valid, nothing saved)
//   RD_CFG_GET                       -> RD_CFG_JSON {json of the config in use}
//   RD_CFG_CLEAR                     -> deletes the stored config, RD_CFG_OK, then restarts
//   RD_TEST <module> [step]          -> runs a module check for the Robo Dev test page:
//                                       RD_TEST_OK <module> [result] or RD_TEST_ERR <module> <reason>
//                                       (speaker, mic and sensor; other modules reply RD_TEST_ERR)
class SerialSetup {
public:
    static constexpr size_t kMaxLine = 4096;

    // sensor_ready: whether the distance sensor answered when the board started.
    // distance_mm: last distance read by the sensor task (negative when nothing is in range).
    SerialSetup(std::function<bool()> sensor_ready, std::function<int()> distance_mm)
        : sensor_ready_(std::move(sensor_ready)), distance_mm_(std::move(distance_mm)) {
#if CONFIG_ESP_CONSOLE_UART
        if (uart_driver_install((uart_port_t)CONFIG_ESP_CONSOLE_UART_NUM, 4096, 0, 0, nullptr, 0) != ESP_OK) {
            ESP_LOGW(TAG, "Serial setup disabled: cannot install UART driver");
            return;
        }
        xTaskCreate([](void* arg) { static_cast<SerialSetup*>(arg)->Run(); },
                    "serial_setup", 6144, this, 2, nullptr);
#elif CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
        usb_serial_jtag_driver_config_t usj = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
        if (usb_serial_jtag_driver_install(&usj) != ESP_OK) {
            ESP_LOGW(TAG, "Serial setup disabled: cannot install USB-Serial/JTAG driver");
            return;
        }
        xTaskCreate([](void* arg) { static_cast<SerialSetup*>(arg)->Run(); },
                    "serial_setup", 6144, this, 2, nullptr);
#endif
    }

private:
    static constexpr const char* TAG = "SerialSetup";
    std::function<bool()> sensor_ready_;
    std::function<int()> distance_mm_;
    volatile bool beeping_ = false;

    void Run() {
        std::string line;
        uint8_t byte;
        while (true) {
#if CONFIG_ESP_CONSOLE_UART
            int n = uart_read_bytes((uart_port_t)CONFIG_ESP_CONSOLE_UART_NUM, &byte, 1, pdMS_TO_TICKS(200));
#else
            int n = usb_serial_jtag_read_bytes(&byte, 1, pdMS_TO_TICKS(200));
#endif
            if (n <= 0) {
                continue;
            }
            if (byte == '\n' || byte == '\r') {
                if (!line.empty()) {
                    Handle(line);
                    line.clear();
                }
            } else if (line.size() < kMaxLine) {
                line.push_back((char)byte);
            } else {
                line.clear();
                Reply("RD_ERR dong lenh qua dai");
            }
        }
    }

    static void Reply(const std::string& text) {
        printf("\n%s\n", text.c_str());
        fflush(stdout);
    }

    static bool StartsWith(const std::string& line, const char* prefix) {
        return line.rfind(prefix, 0) == 0;
    }

    void Handle(const std::string& line) {
        if (StartsWith(line, "RD_PING")) {
            Reply(std::string("RD_PONG ") + esp_app_get_description()->version);
        } else if (StartsWith(line, "RD_INFO")) {
            SendInfo();
        } else if (StartsWith(line, "RD_VOL")) {
            auto codec = Board::GetInstance().GetAudioCodec();
            if (line.size() > sizeof("RD_VOL")) {
                codec->SetOutputVolume(atoi(line.c_str() + sizeof("RD_VOL")));
            }
            Reply("RD_VOL_OK " + std::to_string(codec->output_volume()));
        } else if (StartsWith(line, "RD_TIME")) {
            struct tm tm;
            bool valid = AlarmChime::LocalTime(&tm);
            char text[64];
            strftime(text, sizeof(text), "%Y-%m-%d %H:%M:%S", &tm);
            Reply(std::string("RD_TIME_OK ") + text + " valid=" + (valid ? "1" : "0"));
        } else if (StartsWith(line, "RD_ALARM_TEST")) {
            int index = line.size() > sizeof("RD_ALARM_TEST") ? atoi(line.c_str() + sizeof("RD_ALARM_TEST")) : 0;
            AlarmChime::GetInstance().PlayAsync(index);
            Reply(std::string("RD_ALARM_TEST_OK ") + alarm_chime::kPieces[index % alarm_chime::kPieceCount].name);
        } else if (StartsWith(line, "RD_ALARM")) {
            auto& alarm = AlarmChime::GetInstance();
            if (StartsWith(line, "RD_ALARM ON")) {
                alarm.SetEnabled(true);
            } else if (StartsWith(line, "RD_ALARM OFF")) {
                alarm.SetEnabled(false);
            } else if (StartsWith(line, "RD_ALARM QUIET ")) {
                int from = 0, to = 0;
                if (sscanf(line.c_str() + sizeof("RD_ALARM QUIET"), "%d %d", &from, &to) == 2) {
                    alarm.SetQuietHours(from, to);
                }
            }
            Reply("RD_ALARM_OK enabled=" + std::to_string(alarm.enabled()) +
                  " quiet=" + std::to_string(alarm.quiet_from()) + "-" + std::to_string(alarm.quiet_to()) +
                  " pieces=" + std::to_string(alarm_chime::kPieceCount));
        } else if (StartsWith(line, "RD_SHIFT")) {
            if (line.size() > sizeof("RD_SHIFT")) {
                NoAudioCodec::input_shift = std::clamp(atoi(line.c_str() + sizeof("RD_SHIFT")), 8, 24);
            }
            Reply("RD_SHIFT_OK " + std::to_string(NoAudioCodec::input_shift));
        } else if (StartsWith(line, "RD_TEST ")) {
            HandleTest(line.substr(sizeof("RD_TEST")));
        } else if (StartsWith(line, "RD_MIC")) {
            Reply("RD_MIC_OK " + MicLevel());
        } else if (StartsWith(line, "RD_BEEP_ON")) {
            if (!beeping_) {
                beeping_ = true;
                xTaskCreate([](void* arg) {
                    auto self = static_cast<SerialSetup*>(arg);
                    while (self->beeping_) {
                        Application::GetInstance().PlaySound(Lang::Sounds::OGG_SUCCESS);
                        vTaskDelay(pdMS_TO_TICKS(1000));
                    }
                    vTaskDelete(nullptr);
                }, "beep_loop", 4096, this, 2, nullptr);
            }
            Reply("RD_BEEP_ON_OK");
        } else if (StartsWith(line, "RD_BEEP_OFF")) {
            beeping_ = false;
            Reply("RD_BEEP_OFF_OK");
        } else if (StartsWith(line, "RD_BEEP")) {
            Application::GetInstance().PlaySound(Lang::Sounds::OGG_SUCCESS);
            Reply("RD_BEEP_OK");
        } else if (StartsWith(line, "RD_WIFI_CLEAR")) {
            SsidManager::GetInstance().Clear();
            Reply("RD_WIFI_OK");
            Restart();
        } else if (StartsWith(line, "RD_WIFI ")) {
            cJSON* root = cJSON_Parse(line.c_str() + sizeof("RD_WIFI"));
            cJSON* ssid = root ? cJSON_GetObjectItem(root, "s") : nullptr;
            cJSON* password = root ? cJSON_GetObjectItem(root, "p") : nullptr;
            if (cJSON_IsString(ssid) && ssid->valuestring[0] != '\0') {
                SsidManager::GetInstance().AddSsid(
                    ssid->valuestring, cJSON_IsString(password) ? password->valuestring : "");
                cJSON_Delete(root);
                Reply("RD_WIFI_OK");
                Restart();
            } else {
                cJSON_Delete(root);
                Reply("RD_WIFI_ERR");
            }
        } else if (StartsWith(line, "RD_CFG_GET")) {
            Reply("RD_CFG_JSON " + RobotConfig::Get().ToJson());
        } else if (StartsWith(line, "RD_CFG_CLEAR")) {
            nvs_handle_t handle;
            if (nvs_open("robodev", NVS_READWRITE, &handle) == ESP_OK) {
                nvs_erase_key(handle, "cfg");
                nvs_commit(handle);
                nvs_close(handle);
            }
            Reply("RD_CFG_OK");
            Restart();
        } else if (StartsWith(line, "RD_CFG ")) {
            std::string json = line.substr(sizeof("RD_CFG"));
            if (json.size() > 3900) {
                Reply("RD_CFG_ERR cau hinh qua dai (toi da 3900 byte)");
                return;
            }
            RobotConfig parsed;
            std::string error;
            if (!RobotConfig::Parse(json, parsed, error)) {
                Reply("RD_CFG_ERR " + error);
                return;
            }
            if (!RobotConfig::SaveRaw(json)) {
                Reply("RD_CFG_ERR khong ghi duoc vao NVS");
                return;
            }
            Reply("RD_CFG_OK");
            Restart();
        }
    }

    // Reads 1 s of microphone audio and reports its level (min/max/average of absolute values)
    static std::string MicLevel() {
        auto codec = Board::GetInstance().GetAudioCodec();
        codec->EnableInput(true);
        std::vector<int16_t> buf(512);
        int16_t lo = 32767, hi = -32768;
        int64_t sum_abs = 0;
        int count = 0;
        for (int i = 0; i < 31; i++) {
            if (!codec->InputData(buf)) {
                continue;
            }
            for (int16_t s : buf) {
                lo = std::min(lo, s);
                hi = std::max(hi, s);
                sum_abs += s < 0 ? -s : s;
                count++;
            }
        }
        return "input_enabled=" + std::to_string(codec->input_enabled()) + " samples=" + std::to_string(count) +
               " min=" + std::to_string(lo) + " max=" + std::to_string(hi) +
               " avg_abs=" + std::to_string(count ? (int)(sum_abs / count) : 0);
    }

    void HandleTest(const std::string& args) {
        std::string module = args.substr(0, args.find(' '));
        if (module == "speaker") {
            Application::GetInstance().PlaySound(Lang::Sounds::OGG_SUCCESS);
            Reply("RD_TEST_OK speaker");
        } else if (module == "mic") {
            Reply("RD_TEST_OK mic " + MicLevel());
        } else if (module == "sensor") {
            if (!sensor_ready_ || !sensor_ready_()) {
                Reply("RD_TEST_ERR sensor cam bien khong tra loi tren I2C");
                return;
            }
            int mm = distance_mm_ ? distance_mm_() : -1;
            Reply("RD_TEST_OK sensor mm=" + std::to_string(mm));
        } else {
            Reply("RD_TEST_ERR " + module + " firmware nay chua co bai kiem tra cho module nay");
        }
    }

    void SendInfo() {
        esp_chip_info_t chip;
        esp_chip_info(&chip);
        uint32_t flash_size = 0;
        esp_flash_get_size(nullptr, &flash_size);

        cJSON* root = cJSON_CreateObject();
        cJSON_AddStringToObject(root, "board", "robo-dev-s3");
        cJSON_AddStringToObject(root, "version", esp_app_get_description()->version);
        cJSON_AddStringToObject(root, "idf", esp_app_get_description()->idf_ver);
        cJSON_AddStringToObject(root, "chip", chip.model == CHIP_ESP32S3 ? "esp32s3" : "other");
        cJSON_AddNumberToObject(root, "flash_mb", flash_size / (1024 * 1024));
        cJSON_AddBoolToObject(root, "sensor", sensor_ready_ ? sensor_ready_() : false);
        cJSON_AddBoolToObject(root, "cfg_saved", RobotConfig::HasSaved());
        cJSON_AddBoolToObject(root, "motors", RobotConfig::Get().features.motors);
#if CONFIG_ESP_CONSOLE_UART
        cJSON_AddStringToObject(root, "variant", "uart");
#else
        cJSON_AddStringToObject(root, "variant", "usb");
#endif
        // What this firmware supports; Robo Dev enables pin changes only when "hw" is listed
        cJSON* caps = cJSON_AddArrayToObject(root, "caps");
        for (const char* cap : {"cfg", "wifi", "test"}) {
            cJSON_AddItemToArray(caps, cJSON_CreateString(cap));
        }
        char* printed = cJSON_PrintUnformatted(root);
        Reply(std::string("RD_INFO ") + (printed ? printed : "{}"));
        cJSON_free(printed);
        cJSON_Delete(root);
    }

    static void Restart() {
        vTaskDelay(pdMS_TO_TICKS(600));
        esp_restart();
    }
};

#endif // __SERIAL_SETUP_H__
