#ifndef __ROBOT_LED_H__
#define __ROBOT_LED_H__

#include <cmath>
#include <cstring>
#include <mutex>

#include <driver/gpio.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <led_strip.h>

#include "application.h"
#include "led/led.h"
#include "robot_config.h"

// Onboard RGB LED of "Robo": breathes softly when idle, and shows the mood while speaking.
// Colours and brightness come from RobotConfig (led section).
class RobotLed : public Led {
public:
    explicit RobotLed(gpio_num_t gpio) : cfg_(RobotConfig::Get()) {
        speak_color_ = cfg_.led.speaking;
        if (gpio == GPIO_NUM_NC) {
            return;
        }
        led_strip_config_t strip_config = {};
        strip_config.strip_gpio_num = gpio;
        strip_config.max_leds = 1;
        strip_config.color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB;
        strip_config.led_model = LED_MODEL_WS2812;
        led_strip_rmt_config_t rmt_config = {};
        rmt_config.resolution_hz = 10 * 1000 * 1000;
        ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_config, &rmt_config, &strip_));
        led_strip_clear(strip_);

        esp_timer_create_args_t timer_args = {};
        timer_args.callback = [](void* arg) { static_cast<RobotLed*>(arg)->Tick(); };
        timer_args.arg = this;
        timer_args.dispatch_method = ESP_TIMER_TASK;
        timer_args.name = "robot_led";
        ESP_ERROR_CHECK(esp_timer_create(&timer_args, &timer_));
        ESP_ERROR_CHECK(esp_timer_start_periodic(timer_, kTickUs));
    }

    ~RobotLed() override {
        if (timer_ != nullptr) {
            esp_timer_stop(timer_);
            esp_timer_delete(timer_);
        }
        if (strip_ != nullptr) {
            led_strip_del(strip_);
        }
    }

    void OnStateChanged() override {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto& l = cfg_.led;
        switch (Application::GetInstance().GetDeviceState()) {
            case kDeviceStateStarting:
                Set(Mode::kBlink, l.starting, 100);
                break;
            case kDeviceStateWifiConfiguring:
                Set(Mode::kBlink, l.starting, 500);
                break;
            case kDeviceStateIdle:
                Set(Mode::kBreathe, l.idle, 4000);
                break;
            case kDeviceStateConnecting:
                Set(Mode::kSolid, l.connecting, 0);
                break;
            case kDeviceStateListening:
            case kDeviceStateAudioTesting:
                Set(Mode::kSolid, l.listening, 0);
                break;
            case kDeviceStateSpeaking:
            case kDeviceStateNotifying:
                Set(Mode::kBreathe, speak_color_, kSpeakPeriodMs);
                break;
            case kDeviceStateUpgrading:
                Set(Mode::kBlink, l.upgrading, 100);
                break;
            case kDeviceStateActivating:
                Set(Mode::kBlink, l.activating, 500);
                break;
            default:
                Set(Mode::kOff, RobotConfig::Rgb(), 0);
                break;
        }
    }

    // Called with every emotion shown on the face; the LED takes that mood while speaking.
    void SetEmotion(const char* emotion) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (emotion == nullptr) {
            return;
        }
        auto found = cfg_.led.moods.find(emotion);
        speak_color_ = found != cfg_.led.moods.end() ? found->second : cfg_.led.speaking;
        if (mode_ == Mode::kBreathe && period_ms_ == kSpeakPeriodMs) {
            color_ = speak_color_;
        }
    }

private:
    enum class Mode { kOff, kSolid, kBlink, kBreathe };
    static constexpr int64_t kTickUs = 30 * 1000;
    static constexpr int kSpeakPeriodMs = 1200;

    const RobotConfig& cfg_;
    led_strip_handle_t strip_ = nullptr;
    esp_timer_handle_t timer_ = nullptr;
    std::mutex mutex_;
    Mode mode_ = Mode::kOff;
    RobotConfig::Rgb color_;
    RobotConfig::Rgb speak_color_;
    int period_ms_ = 0;
    int64_t started_us_ = 0;

    void Set(Mode mode, const RobotConfig::Rgb& color, int period_ms) {
        mode_ = mode;
        color_ = color;
        period_ms_ = period_ms;
        started_us_ = esp_timer_get_time();
    }

    void Tick() {
        std::lock_guard<std::mutex> lock(mutex_);
        float level = 0;
        float elapsed_ms = (esp_timer_get_time() - started_us_) / 1000.0f;
        switch (mode_) {
            case Mode::kOff:
                level = 0;
                break;
            case Mode::kSolid:
                level = 1;
                break;
            case Mode::kBlink:
                level = ((int)(elapsed_ms / period_ms_) % 2 == 0) ? 1 : 0;
                break;
            case Mode::kBreathe:
                // 0.15 .. 1.0 smooth sine
                level = 0.575f + 0.425f * sinf(elapsed_ms / period_ms_ * 2 * (float)M_PI);
                break;
        }
        level *= cfg_.led.brightness / 100.0f;
        led_strip_set_pixel(strip_, 0, (uint8_t)(color_.r * level), (uint8_t)(color_.g * level),
                            (uint8_t)(color_.b * level));
        led_strip_refresh(strip_);
    }
};

#endif // __ROBOT_LED_H__
