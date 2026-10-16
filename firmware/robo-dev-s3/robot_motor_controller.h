#ifndef __ROBOT_MOTOR_CONTROLLER_H__
#define __ROBOT_MOTOR_CONTROLLER_H__

#include <functional>
#include <string>
#include <utility>

#include <driver/gpio.h>
#include <driver/ledc.h>
#include <esp_timer.h>

#include "mcp_server.h"
#include "robot_config.h"

// Drives two DC motors through a 4-input H-bridge (IN1/IN2 = motor A, IN3/IN4 = motor B).
// Each input is a PWM channel, so the speed is adjustable. The movement is also exposed as
// MCP tools so the AI can drive the robot. Speeds, wheel direction and which tools exist come
// from RobotConfig.
class RobotMotorController {
public:
    enum Dir { kStop, kForward, kBackward };

    bool IsMovingForward() const { return moving_forward_; }
    bool IsMoving() const { return moving_; }
    int default_speed() const { return cfg_.motors.default_speed; }
    int slow_speed() const { return cfg_.motors.slow_speed; }

    void Stop() { Drive(kStop, kStop, 0, 0); }

    // Left/right wheel directions, speed in percent, runs for duration_ms then stops by itself.
    void Drive(Dir left, Dir right, int speed, int duration_ms) {
        esp_timer_stop(stop_timer_);
        bool forward = (left == kForward && right == kForward);
        if (cfg_.motors.swap_sides) {
            std::swap(left, right);
        }
        if (cfg_.motors.invert_left) {
            left = Flip(left);
        }
        if (cfg_.motors.invert_right) {
            right = Flip(right);
        }
        SetMotor(0, left, speed);
        SetMotor(1, right, speed);
        moving_ = left != kStop || right != kStop;
        moving_forward_ = forward;
        if (moving_) {
            esp_timer_start_once(stop_timer_, (uint64_t)duration_ms * 1000);
        }
    }

    void Forward(int speed, int ms) { Drive(kForward, kForward, speed, ms); }
    void Backward(int speed, int ms) { Drive(kBackward, kBackward, speed, ms); }
    void TurnLeft(int speed, int ms) { Drive(kBackward, kForward, speed, ms); }
    void TurnRight(int speed, int ms) { Drive(kForward, kBackward, speed, ms); }

    RobotMotorController(gpio_num_t in1, gpio_num_t in2, gpio_num_t in3, gpio_num_t in4)
        : pins_{in1, in2, in3, in4}, cfg_(RobotConfig::Get()) {
        ledc_timer_config_t timer_config = {};
        timer_config.speed_mode = LEDC_LOW_SPEED_MODE;
        timer_config.duty_resolution = LEDC_TIMER_8_BIT;
        timer_config.timer_num = LEDC_TIMER_1;
        timer_config.freq_hz = 5000;
        timer_config.clk_cfg = LEDC_AUTO_CLK;
        ESP_ERROR_CHECK(ledc_timer_config(&timer_config));

        for (int i = 0; i < 4; i++) {
            ledc_channel_config_t channel_config = {};
            channel_config.gpio_num = pins_[i];
            channel_config.speed_mode = LEDC_LOW_SPEED_MODE;
            channel_config.channel = (ledc_channel_t)(LEDC_CHANNEL_2 + i);
            channel_config.timer_sel = LEDC_TIMER_1;
            channel_config.duty = 0;
            channel_config.hpoint = 0;
            ESP_ERROR_CHECK(ledc_channel_config(&channel_config));
        }

        esp_timer_create_args_t timer_args = {};
        timer_args.callback = [](void* arg) {
            auto self = static_cast<RobotMotorController*>(arg);
            self->SetMotor(0, kStop, 0);
            self->SetMotor(1, kStop, 0);
            self->moving_ = false;
            self->moving_forward_ = false;
        };
        timer_args.arg = this;
        timer_args.name = "robot_motor_stop";
        ESP_ERROR_CHECK(esp_timer_create(&timer_args, &stop_timer_));

        RegisterTools();
    }

private:
    gpio_num_t pins_[4];
    const RobotConfig& cfg_;
    esp_timer_handle_t stop_timer_ = nullptr;
    volatile bool moving_ = false;
    volatile bool moving_forward_ = false;

    static Dir Flip(Dir dir) {
        return dir == kForward ? kBackward : (dir == kBackward ? kForward : kStop);
    }

    void SetDuty(int pin_index, int percent) {
        auto channel = (ledc_channel_t)(LEDC_CHANNEL_2 + pin_index);
        uint32_t duty = (uint32_t)(percent < 0 ? 0 : (percent > 100 ? 100 : percent)) * 255 / 100;
        ledc_set_duty(LEDC_LOW_SPEED_MODE, channel, duty);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, channel);
    }

    void SetMotor(int index, Dir dir, int speed) {
        SetDuty(index * 2, dir == kForward ? speed : 0);
        SetDuty(index * 2 + 1, dir == kBackward ? speed : 0);
    }

    // Registers one movement tool unless the config turns it off.
    void AddMoveTool(const char* name, const char* default_description,
                     std::function<void(int speed, int ms)> move) {
        const auto& tool = cfg_.tools.at(name);
        if (!tool.enabled) {
            ESP_LOGI("RobotMotor", "Tool self.robot.%s disabled by config", name);
            return;
        }
        int speed = tool.speed >= 0 ? tool.speed : cfg_.motors.default_speed;
        int duration = tool.duration_ms >= 0 ? tool.duration_ms : 1000;
        const std::string description = tool.description.empty() ? default_description : tool.description;
        McpServer::GetInstance().AddTool(
            std::string("self.robot.") + name, description,
            PropertyList({Property("duration_ms", kPropertyTypeInteger, duration, 100, 10000),
                          Property("speed", kPropertyTypeInteger, speed, 30, 100)}),
            [move](const PropertyList& properties) -> ReturnValue {
                move(properties["speed"].value<int>(), properties["duration_ms"].value<int>());
                return true;
            });
    }

    void RegisterTools() {
        AddMoveTool("forward",
                    "Move the robot forward. It stops automatically after duration_ms milliseconds, "
                    "or earlier if an obstacle is in front. speed is a percentage (30-100).",
                    [this](int speed, int ms) { Forward(speed, ms); });
        AddMoveTool("backward",
                    "Move the robot backward. It stops automatically after duration_ms milliseconds. "
                    "speed is a percentage (30-100).",
                    [this](int speed, int ms) { Backward(speed, ms); });
        AddMoveTool("turn_left",
                    "Turn the robot left in place. It stops automatically after duration_ms milliseconds. "
                    "speed is a percentage (30-100).",
                    [this](int speed, int ms) { TurnLeft(speed, ms); });
        AddMoveTool("turn_right",
                    "Turn the robot right in place. It stops automatically after duration_ms milliseconds. "
                    "speed is a percentage (30-100).",
                    [this](int speed, int ms) { TurnRight(speed, ms); });

        const auto& stop_tool = cfg_.tools.at("stop");
        if (stop_tool.enabled) {
            McpServer::GetInstance().AddTool(
                "self.robot.stop",
                stop_tool.description.empty() ? "Stop the robot immediately." : stop_tool.description,
                PropertyList(),
                [this](const PropertyList& properties) -> ReturnValue {
                    Stop();
                    return true;
                });
        }
    }
};

#endif // __ROBOT_MOTOR_CONTROLLER_H__
