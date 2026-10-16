#ifndef __ROBOT_WEATHER_H__
#define __ROBOT_WEATHER_H__

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <string>

#include <cJSON.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "board.h"

// Current weather for the robot's location. The location comes from the public IP
// (ip-api.com), the weather from open-meteo.com; neither needs an API key.
// Refresh() starts a background fetch (at most one at a time, results cached for 30 minutes).
class RobotWeather {
public:
    static RobotWeather& GetInstance() {
        static RobotWeather instance;
        return instance;
    }

    // Short text such as "Ha Noi 28C Troi nang", "..." while loading, "--" when it failed.
    std::string Text() {
        if (state_ == kLoading) return "...";
        if (state_ == kFailed || state_ == kIdle) return "--";
        return text_;
    }

    void Refresh() {
        int64_t now = esp_timer_get_time();
        if (state_ == kLoading) return;
        if (state_ == kReady && now - fetched_at_ < kCacheUs) return;
        if (state_ == kFailed && now - fetched_at_ < kRetryUs) return;
        state_ = kLoading;
        if (xTaskCreate([](void*) {
                RobotWeather& w = RobotWeather::GetInstance();
                bool ok = w.Fetch();
                w.fetched_at_ = esp_timer_get_time();
                w.state_ = ok ? kReady : kFailed;
                vTaskDelete(nullptr);
            }, "robot_weather", 6144, nullptr, 2, nullptr) != pdPASS) {
            state_ = kFailed;
            fetched_at_ = now;
        }
    }

private:
    enum State { kIdle, kLoading, kReady, kFailed };
    static constexpr int64_t kCacheUs = 30LL * 60 * 1000000;
    static constexpr int64_t kRetryUs = 60LL * 1000000;
    static constexpr const char* TAG = "RobotWeather";

    std::atomic<int> state_{kIdle};
    int64_t fetched_at_ = 0;
    std::string text_;

    static bool Get(const std::string& url, std::string& body) {
        auto network = Board::GetInstance().GetNetwork();
        auto http = network->CreateHttp(0);
        http->SetTimeout(8000);
        if (!http->Open("GET", url)) {
            return false;
        }
        auto status = http->GetStatusCode();
        if (!status || *status != 200) {
            http->Close();
            return false;
        }
        body = http->ReadAll();
        http->Close();
        return !body.empty();
    }

    static const char* Describe(int code) {  // WMO weather code, no diacritics (the font is basic Latin)
        if (code == 0) return "Troi nang";
        if (code <= 3) return "Co may";
        if (code == 45 || code == 48) return "Suong mu";
        if (code >= 51 && code <= 57) return "Mua phun";
        if (code >= 61 && code <= 67) return "Mua";
        if (code >= 71 && code <= 77) return "Tuyet";
        if (code >= 80 && code <= 82) return "Mua rao";
        if (code >= 95) return "Giong";
        return "Khac";
    }

    bool Fetch() {
        std::string body;
        if (!Get("http://ip-api.com/json/?fields=status,city,lat,lon", body)) {
            ESP_LOGW(TAG, "Cannot get location");
            return false;
        }
        cJSON* loc = cJSON_Parse(body.c_str());
        if (loc == nullptr) return false;
        cJSON* lat = cJSON_GetObjectItem(loc, "lat");
        cJSON* lon = cJSON_GetObjectItem(loc, "lon");
        cJSON* city = cJSON_GetObjectItem(loc, "city");
        if (!cJSON_IsNumber(lat) || !cJSON_IsNumber(lon)) {
            cJSON_Delete(loc);
            return false;
        }
        char url[200];
        snprintf(url, sizeof(url),
                 "https://api.open-meteo.com/v1/forecast?latitude=%.3f&longitude=%.3f"
                 "&current=temperature_2m,weather_code",
                 lat->valuedouble, lon->valuedouble);
        std::string city_name = cJSON_IsString(city) ? city->valuestring : "";
        cJSON_Delete(loc);

        if (!Get(url, body)) {
            ESP_LOGW(TAG, "Cannot get weather");
            return false;
        }
        cJSON* root = cJSON_Parse(body.c_str());
        if (root == nullptr) return false;
        cJSON* cur = cJSON_GetObjectItem(root, "current");
        cJSON* temp = cur ? cJSON_GetObjectItem(cur, "temperature_2m") : nullptr;
        cJSON* code = cur ? cJSON_GetObjectItem(cur, "weather_code") : nullptr;
        bool ok = cJSON_IsNumber(temp) && cJSON_IsNumber(code);
        if (ok) {
            char line[96];
            snprintf(line, sizeof(line), "%.0fC  %s", temp->valuedouble, Describe(code->valueint));
            text_ = city_name.empty() ? line : city_name.substr(0, 20) + "\n" + line;
            ESP_LOGI(TAG, "Weather: %s", line);
        }
        cJSON_Delete(root);
        return ok;
    }
};

#endif  // __ROBOT_WEATHER_H__
