#ifndef __ROBOT_BEHAVIOR_H__
#define __ROBOT_BEHAVIOR_H__

#include <cstring>
#include <functional>

#include <esp_log.h>
#include <esp_random.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "application.h"
#include "board.h"
#include "config.h"
#include "mcp_server.h"
#include "robot_motor_controller.h"
#include "vl6180x.h"
#include "robot_config.h"

// Personality of the robot "Robo": moves with its emotions, reacts to obstacles
// and can wander around on its own. Every number comes from RobotConfig.
class RobotBehavior {
public:
    RobotBehavior(RobotMotorController* motors, std::function<int()> get_distance_mm, bool has_sensor)
        : motors_(motors), cfg_(RobotConfig::Get()), get_distance_mm_(std::move(get_distance_mm)),
          has_sensor_(has_sensor) {
        last_report_us_ = -(int64_t)cfg_.obstacle.report_interval_ms * 1000;

        const auto& tool = cfg_.tools.at("set_wander");
        if (tool.enabled) {
            McpServer::GetInstance().AddTool("self.robot.set_wander",
                tool.description.empty()
                    ? "Turn the robot's wander mode on or off. In wander mode the robot walks around by "
                      "itself while idle and avoids obstacles. Keep it off when the robot is on a table."
                    : tool.description,
                PropertyList({Property("enabled", kPropertyTypeBoolean)}),
                [this](const PropertyList& properties) -> ReturnValue {
                    // Never wander blind: it needs the distance sensor to avoid obstacles
                    wander_ = has_sensor_ && properties["enabled"].value<bool>();
                    last_wander_us_ = esp_timer_get_time();
                    return wander_;
                });
            xTaskCreate([](void* arg) { static_cast<RobotBehavior*>(arg)->WanderTask(); },
                        "robot_wander", 3072, this, 2, nullptr);
        } else {
            ESP_LOGI(TAG, "Tool self.robot.set_wander disabled by config");
        }
    }

    // Called with every emotion shown on the face (happy, sad, ...). Moves the robot to match.
    void OnEmotion(const char* emotion) {
        if (!cfg_.features.emotion_motion || emotion == nullptr || motors_->IsMoving()) {
            return;
        }
        auto found = cfg_.emotion_motion.map.find(emotion);
        if (found == cfg_.emotion_motion.map.end() || found->second.action == RobotConfig::Action::kNone) {
            return;
        }
        int64_t now = esp_timer_get_time();
        if (now - last_emotion_move_us_ < (int64_t)cfg_.emotion_motion.cooldown_ms * 1000) {
            return;
        }
        const auto& motion = found->second;
        switch (motion.action) {
            case RobotConfig::Action::kSpinRight: motors_->TurnRight(motion.speed, motion.ms); break;
            case RobotConfig::Action::kSpinLeft: motors_->TurnLeft(motion.speed, motion.ms); break;
            case RobotConfig::Action::kBackward: motors_->Backward(motion.speed, motion.ms); break;
            case RobotConfig::Action::kForward: motors_->Forward(motion.speed, motion.ms); break;
            default: return;
        }
        last_emotion_move_us_ = now;
    }

    // Called when the robot was driving forward and the sensor saw something close.
    void OnObstacle(int distance_mm) {
        ESP_LOGW(TAG, "Obstacle at %d mm", distance_mm);
        if (cfg_.obstacle.back_off_ms > 0) {
            motors_->Backward(motors_->slow_speed(), cfg_.obstacle.back_off_ms);
        }
        auto display = Board::GetInstance().GetDisplay();
        if (display != nullptr) {
            display->SetEmotion("surprised");
        }

        // Let the AI react in character ("Ai, dung chan duong minh!") at most once in a while
        if (!cfg_.features.obstacle_report) {
            return;
        }
        int64_t now = esp_timer_get_time();
        if (now - last_report_us_ < (int64_t)cfg_.obstacle.report_interval_ms * 1000) {
            return;
        }
        auto& app = Application::GetInstance();
        if (app.GetDeviceState() != kDeviceStateIdle) {
            return;
        }
        last_report_us_ = now;
        std::string text = cfg_.obstacle.report_text;
        app.Schedule([text]() { Application::GetInstance().WakeWordInvoke(text); });
    }

    bool wander() const { return wander_; }

private:
    static constexpr const char* TAG = "RobotBehavior";

    RobotMotorController* motors_;
    const RobotConfig& cfg_;
    std::function<int()> get_distance_mm_;
    bool has_sensor_;
    volatile bool wander_ = false;
    int64_t last_emotion_move_us_ = 0;
    int64_t last_report_us_ = 0;
    int64_t last_wander_us_ = 0;

    static int RandomBetween(int low, int high) {
        return low + (int)(esp_random() % (uint32_t)(high - low + 1));
    }

    void WanderTask() {
        const auto& w = cfg_.wander;
        int64_t next_after_us = (int64_t)RandomBetween(w.interval_min_ms, w.interval_max_ms) * 1000;
        while (true) {
            vTaskDelay(pdMS_TO_TICKS(500));
            if (!wander_ || motors_->IsMoving() ||
                Application::GetInstance().GetDeviceState() != kDeviceStateIdle) {
                continue;
            }
            int64_t now = esp_timer_get_time();
            if (now - last_wander_us_ < next_after_us) {
                continue;
            }
            last_wander_us_ = now;
            next_after_us = (int64_t)RandomBetween(w.interval_min_ms, w.interval_max_ms) * 1000;

            int distance = get_distance_mm_();
            bool path_clear = distance == Vl6180x::kOutOfRange || distance > w.clear_distance_mm;
            int choice = RandomBetween(0, 3);
            if (choice <= 1 && path_clear) {
                motors_->Forward(w.forward_speed, RandomBetween(1000, 2000));
            } else if (choice == 2 || !path_clear) {
                motors_->TurnLeft(w.turn_speed, RandomBetween(400, 900));
            } else {
                motors_->TurnRight(w.turn_speed, RandomBetween(400, 900));
            }
        }
    }
};

#endif // __ROBOT_BEHAVIOR_H__
