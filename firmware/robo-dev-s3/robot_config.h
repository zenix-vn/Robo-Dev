#ifndef __ROBOT_CONFIG_H__
#define __ROBOT_CONFIG_H__

#include <cstdint>
#include <cstring>
#include <map>
#include <string>

#include <cJSON.h>
#include <esp_log.h>
#include <nvs.h>
#include <nvs_flash.h>

// Runtime configuration of the Robo robot. Defaults reproduce the behaviour the firmware had
// before the config existed, so a board that never received a config behaves the same.
// The config is a JSON document stored in NVS (namespace "robodev", key "cfg"); Robo Dev sends it
// with the RD_CFG serial command.
class RobotConfig {
public:
    enum class Action { kNone, kSpinRight, kSpinLeft, kBackward, kForward };

    struct Motion {
        Action action = Action::kNone;
        int speed = 70;
        int ms = 1000;
    };

    struct Rgb {
        uint8_t r = 0, g = 0, b = 0;
    };

    struct Tool {
        bool enabled = true;
        std::string description;  // empty = built-in description
        int speed = -1;           // -1 = motors.default_speed
        int duration_ms = -1;     // -1 = 1000
    };

    struct {
        bool motors = true;
        bool obstacle_stop = true;
        bool obstacle_report = true;
        bool emotion_motion = true;
        bool led = true;
        bool hide_subtitle = true;
    } features;

    struct {
        int default_speed = 70;
        int slow_speed = 45;
        bool invert_left = false;
        bool invert_right = false;
        bool swap_sides = false;
    } motors;

    struct {
        int stop_distance_mm = 150;
        int back_off_ms = 500;
        int report_interval_ms = 20000;
        std::string report_text = "[Robo vừa chạm phải vật cản phía trước và đã lùi lại]";
    } obstacle;

    struct {
        int cooldown_ms = 4000;
        std::map<std::string, Motion> map;
    } emotion_motion;

    struct {
        int interval_min_ms = 8000;
        int interval_max_ms = 20000;
        int forward_speed = 55;
        int turn_speed = 60;
        int clear_distance_mm = 400;
    } wander;

    struct {
        int brightness = 6;  // percent of the colour values below
        Rgb idle{255, 145, 36};
        Rgb listening{0, 255, 255};
        Rgb speaking{255, 96, 0};
        Rgb connecting{0, 0, 255};
        Rgb starting{0, 0, 255};
        Rgb activating{0, 255, 0};
        Rgb upgrading{0, 255, 0};
        std::map<std::string, Rgb> moods;
    } led;

    std::map<std::string, Tool> tools;

    static RobotConfig& Get() {
        static RobotConfig instance = LoadFromNvs();
        return instance;
    }

    RobotConfig() { SetDefaults(); }

    // Parses a config document over the defaults. Returns false and sets `error` on invalid input.
    static bool Parse(const std::string& json, RobotConfig& out, std::string& error) {
        cJSON* root = cJSON_Parse(json.c_str());
        if (root == nullptr || !cJSON_IsObject(root)) {
            cJSON_Delete(root);
            error = "JSON khong hop le";
            return false;
        }
        RobotConfig cfg;
        bool ok = cfg.Overlay(root, error);
        cJSON_Delete(root);
        if (!ok) {
            return false;
        }
        out = cfg;
        return true;
    }

    std::string ToJson() const {
        cJSON* root = cJSON_CreateObject();
        cJSON_AddNumberToObject(root, "version", 1);

        cJSON* f = cJSON_AddObjectToObject(root, "features");
        cJSON_AddBoolToObject(f, "motors", features.motors);
        cJSON_AddBoolToObject(f, "obstacle_stop", features.obstacle_stop);
        cJSON_AddBoolToObject(f, "obstacle_report", features.obstacle_report);
        cJSON_AddBoolToObject(f, "emotion_motion", features.emotion_motion);
        cJSON_AddBoolToObject(f, "led", features.led);
        cJSON_AddBoolToObject(f, "hide_subtitle", features.hide_subtitle);

        cJSON* m = cJSON_AddObjectToObject(root, "motors");
        cJSON_AddNumberToObject(m, "default_speed", motors.default_speed);
        cJSON_AddNumberToObject(m, "slow_speed", motors.slow_speed);
        cJSON_AddBoolToObject(m, "invert_left", motors.invert_left);
        cJSON_AddBoolToObject(m, "invert_right", motors.invert_right);
        cJSON_AddBoolToObject(m, "swap_sides", motors.swap_sides);

        cJSON* o = cJSON_AddObjectToObject(root, "obstacle");
        cJSON_AddNumberToObject(o, "stop_distance_mm", obstacle.stop_distance_mm);
        cJSON_AddNumberToObject(o, "back_off_ms", obstacle.back_off_ms);
        cJSON_AddNumberToObject(o, "report_interval_ms", obstacle.report_interval_ms);
        cJSON_AddStringToObject(o, "report_text", obstacle.report_text.c_str());

        cJSON* e = cJSON_AddObjectToObject(root, "emotion_motion");
        cJSON_AddNumberToObject(e, "cooldown_ms", emotion_motion.cooldown_ms);
        for (const auto& [name, motion] : emotion_motion.map) {
            cJSON* item = cJSON_AddObjectToObject(e, name.c_str());
            cJSON_AddStringToObject(item, "action", ActionName(motion.action));
            cJSON_AddNumberToObject(item, "speed", motion.speed);
            cJSON_AddNumberToObject(item, "ms", motion.ms);
        }

        cJSON* w = cJSON_AddObjectToObject(root, "wander");
        cJSON_AddNumberToObject(w, "interval_min_ms", wander.interval_min_ms);
        cJSON_AddNumberToObject(w, "interval_max_ms", wander.interval_max_ms);
        cJSON_AddNumberToObject(w, "forward_speed", wander.forward_speed);
        cJSON_AddNumberToObject(w, "turn_speed", wander.turn_speed);
        cJSON_AddNumberToObject(w, "clear_distance_mm", wander.clear_distance_mm);

        cJSON* l = cJSON_AddObjectToObject(root, "led");
        cJSON_AddNumberToObject(l, "brightness", led.brightness);
        AddRgb(l, "idle", led.idle);
        AddRgb(l, "listening", led.listening);
        AddRgb(l, "speaking", led.speaking);
        AddRgb(l, "connecting", led.connecting);
        AddRgb(l, "starting", led.starting);
        AddRgb(l, "activating", led.activating);
        AddRgb(l, "upgrading", led.upgrading);
        cJSON* moods = cJSON_AddObjectToObject(l, "moods");
        for (const auto& [name, rgb] : led.moods) {
            AddRgb(moods, name.c_str(), rgb);
        }

        cJSON* t = cJSON_AddObjectToObject(root, "mcp_tools");
        for (const auto& [name, tool] : tools) {
            cJSON* item = cJSON_AddObjectToObject(t, name.c_str());
            cJSON_AddBoolToObject(item, "enabled", tool.enabled);
            if (!tool.description.empty()) {
                cJSON_AddStringToObject(item, "description", tool.description.c_str());
            }
            if (tool.speed >= 0) {
                cJSON_AddNumberToObject(item, "speed", tool.speed);
            }
            if (tool.duration_ms >= 0) {
                cJSON_AddNumberToObject(item, "duration_ms", tool.duration_ms);
            }
        }

        char* printed = cJSON_PrintUnformatted(root);
        std::string text = printed ? printed : "{}";
        cJSON_free(printed);
        cJSON_Delete(root);
        return text;
    }

    static bool SaveRaw(const std::string& json) {
        nvs_handle_t handle;
        if (nvs_open("robodev", NVS_READWRITE, &handle) != ESP_OK) {
            return false;
        }
        bool ok = nvs_set_str(handle, "cfg", json.c_str()) == ESP_OK && nvs_commit(handle) == ESP_OK;
        nvs_close(handle);
        return ok;
    }

    static bool HasSaved() {
        nvs_handle_t handle;
        if (nvs_open("robodev", NVS_READONLY, &handle) != ESP_OK) {
            return false;
        }
        size_t size = 0;
        bool has = nvs_get_str(handle, "cfg", nullptr, &size) == ESP_OK && size > 1;
        nvs_close(handle);
        return has;
    }

    static const char* ActionName(Action action) {
        switch (action) {
            case Action::kSpinRight: return "spin_right";
            case Action::kSpinLeft: return "spin_left";
            case Action::kBackward: return "backward";
            case Action::kForward: return "forward";
            default: return "none";
        }
    }

private:
    static constexpr const char* TAG = "RobotConfig";

    void SetDefaults() {
        // Same actions the firmware had hard-coded before the config existed
        for (const char* name : {"happy", "laughing", "funny", "loving", "kissy", "winking", "silly"}) {
            emotion_motion.map[name] = {Action::kSpinRight, 70, 1500};
        }
        for (const char* name : {"sad", "crying"}) {
            emotion_motion.map[name] = {Action::kBackward, 45, 1000};
        }
        for (const char* name : {"surprised", "shocked"}) {
            emotion_motion.map[name] = {Action::kBackward, 70, 250};
        }
        for (const char* name : {"happy", "laughing", "funny", "silly", "winking"}) {
            led.moods[name] = {255, 191, 0};
        }
        for (const char* name : {"sad", "crying"}) {
            led.moods[name] = {0, 48, 255};
        }
        led.moods["angry"] = {255, 0, 0};
        for (const char* name : {"loving", "kissy", "embarrassed"}) {
            led.moods[name] = {255, 32, 96};
        }
        for (const char* name : {"surprised", "shocked"}) {
            led.moods[name] = {255, 255, 255};
        }
        for (const char* name : {"thinking", "confused"}) {
            led.moods[name] = {128, 0, 192};
        }
        for (const char* name : {"cool", "confident", "relaxed"}) {
            led.moods[name] = {0, 255, 128};
        }
        for (const char* name : {"forward", "backward", "turn_left", "turn_right", "stop",
                                 "set_wander", "get_distance"}) {
            tools[name] = Tool();
        }
    }

    static RobotConfig LoadFromNvs() {
        RobotConfig cfg;
        nvs_handle_t handle;
        if (nvs_open("robodev", NVS_READONLY, &handle) != ESP_OK) {
            return cfg;
        }
        size_t size = 0;
        if (nvs_get_str(handle, "cfg", nullptr, &size) == ESP_OK && size > 1) {
            std::string json(size, '\0');
            if (nvs_get_str(handle, "cfg", json.data(), &size) == ESP_OK) {
                json.resize(strlen(json.c_str()));
                std::string error;
                RobotConfig parsed;
                if (Parse(json, parsed, error)) {
                    ESP_LOGI(TAG, "Loaded saved config (%d bytes)", (int)json.size());
                    cfg = parsed;
                } else {
                    ESP_LOGW(TAG, "Saved config ignored: %s", error.c_str());
                }
            }
        }
        nvs_close(handle);
        return cfg;
    }

    static void AddRgb(cJSON* parent, const char* name, const Rgb& rgb) {
        cJSON* array = cJSON_AddArrayToObject(parent, name);
        cJSON_AddItemToArray(array, cJSON_CreateNumber(rgb.r));
        cJSON_AddItemToArray(array, cJSON_CreateNumber(rgb.g));
        cJSON_AddItemToArray(array, cJSON_CreateNumber(rgb.b));
    }

    // ---- parsing helpers: leave the value alone when the key is missing
    static bool GetBool(cJSON* obj, const char* key, bool& value, std::string& error) {
        cJSON* item = cJSON_GetObjectItem(obj, key);
        if (item == nullptr) {
            return true;
        }
        if (!cJSON_IsBool(item)) {
            error = std::string(key) + " phai la true/false";
            return false;
        }
        value = cJSON_IsTrue(item);
        return true;
    }

    static bool GetInt(cJSON* obj, const char* key, int& value, int low, int high, std::string& error) {
        cJSON* item = cJSON_GetObjectItem(obj, key);
        if (item == nullptr) {
            return true;
        }
        if (!cJSON_IsNumber(item) || item->valueint < low || item->valueint > high) {
            error = std::string(key) + " phai trong khoang " + std::to_string(low) + "-" + std::to_string(high);
            return false;
        }
        value = item->valueint;
        return true;
    }

    static bool GetString(cJSON* obj, const char* key, std::string& value, size_t max_len, std::string& error) {
        cJSON* item = cJSON_GetObjectItem(obj, key);
        if (item == nullptr) {
            return true;
        }
        if (!cJSON_IsString(item) || strlen(item->valuestring) > max_len) {
            error = std::string(key) + " phai la chuoi toi da " + std::to_string(max_len) + " ky tu";
            return false;
        }
        value = item->valuestring;
        return true;
    }

    static bool GetRgb(cJSON* obj, const char* key, Rgb& value, std::string& error) {
        cJSON* item = cJSON_GetObjectItem(obj, key);
        if (item == nullptr) {
            return true;
        }
        if (!cJSON_IsArray(item) || cJSON_GetArraySize(item) != 3) {
            error = std::string(key) + " phai la [r,g,b]";
            return false;
        }
        int c[3];
        for (int i = 0; i < 3; i++) {
            cJSON* v = cJSON_GetArrayItem(item, i);
            if (!cJSON_IsNumber(v) || v->valueint < 0 || v->valueint > 255) {
                error = std::string(key) + " moi mau phai trong khoang 0-255";
                return false;
            }
            c[i] = v->valueint;
        }
        value = {(uint8_t)c[0], (uint8_t)c[1], (uint8_t)c[2]};
        return true;
    }

    static bool ParseAction(const char* text, Action& action) {
        static const std::pair<const char*, Action> names[] = {
            {"none", Action::kNone}, {"spin_right", Action::kSpinRight}, {"spin_left", Action::kSpinLeft},
            {"backward", Action::kBackward}, {"forward", Action::kForward}};
        for (const auto& [name, value] : names) {
            if (strcmp(text, name) == 0) {
                action = value;
                return true;
            }
        }
        return false;
    }

    bool Overlay(cJSON* root, std::string& error) {
        if (cJSON* f = cJSON_GetObjectItem(root, "features"); cJSON_IsObject(f)) {
            if (!GetBool(f, "motors", features.motors, error) ||
                !GetBool(f, "obstacle_stop", features.obstacle_stop, error) ||
                !GetBool(f, "obstacle_report", features.obstacle_report, error) ||
                !GetBool(f, "emotion_motion", features.emotion_motion, error) ||
                !GetBool(f, "led", features.led, error) ||
                !GetBool(f, "hide_subtitle", features.hide_subtitle, error)) {
                return false;
            }
        }
        if (cJSON* m = cJSON_GetObjectItem(root, "motors"); cJSON_IsObject(m)) {
            if (!GetInt(m, "default_speed", motors.default_speed, 30, 100, error) ||
                !GetInt(m, "slow_speed", motors.slow_speed, 30, 100, error) ||
                !GetBool(m, "invert_left", motors.invert_left, error) ||
                !GetBool(m, "invert_right", motors.invert_right, error) ||
                !GetBool(m, "swap_sides", motors.swap_sides, error)) {
                return false;
            }
        }
        if (cJSON* o = cJSON_GetObjectItem(root, "obstacle"); cJSON_IsObject(o)) {
            if (!GetInt(o, "stop_distance_mm", obstacle.stop_distance_mm, 50, 1000, error) ||
                !GetInt(o, "back_off_ms", obstacle.back_off_ms, 0, 3000, error) ||
                !GetInt(o, "report_interval_ms", obstacle.report_interval_ms, 1000, 600000, error) ||
                !GetString(o, "report_text", obstacle.report_text, 200, error)) {
                return false;
            }
        }
        if (cJSON* e = cJSON_GetObjectItem(root, "emotion_motion"); cJSON_IsObject(e)) {
            if (!GetInt(e, "cooldown_ms", emotion_motion.cooldown_ms, 0, 60000, error)) {
                return false;
            }
            for (cJSON* item = e->child; item != nullptr; item = item->next) {
                if (strcmp(item->string, "cooldown_ms") == 0) {
                    continue;
                }
                if (!cJSON_IsObject(item) || strlen(item->string) > 24 || emotion_motion.map.size() > 40) {
                    error = std::string("emotion_motion.") + item->string + " khong hop le";
                    return false;
                }
                Motion motion = emotion_motion.map.count(item->string) ? emotion_motion.map[item->string] : Motion();
                cJSON* action = cJSON_GetObjectItem(item, "action");
                if (action != nullptr && (!cJSON_IsString(action) || !ParseAction(action->valuestring, motion.action))) {
                    error = std::string(item->string) + ".action khong hop le";
                    return false;
                }
                if (!GetInt(item, "speed", motion.speed, 30, 100, error) ||
                    !GetInt(item, "ms", motion.ms, 100, 10000, error)) {
                    return false;
                }
                emotion_motion.map[item->string] = motion;
            }
        }
        if (cJSON* w = cJSON_GetObjectItem(root, "wander"); cJSON_IsObject(w)) {
            if (!GetInt(w, "interval_min_ms", wander.interval_min_ms, 1000, 600000, error) ||
                !GetInt(w, "interval_max_ms", wander.interval_max_ms, 1000, 600000, error) ||
                !GetInt(w, "forward_speed", wander.forward_speed, 30, 100, error) ||
                !GetInt(w, "turn_speed", wander.turn_speed, 30, 100, error) ||
                !GetInt(w, "clear_distance_mm", wander.clear_distance_mm, 100, 2000, error)) {
                return false;
            }
            if (wander.interval_min_ms > wander.interval_max_ms) {
                error = "wander.interval_min_ms phai nho hon hoac bang interval_max_ms";
                return false;
            }
        }
        if (cJSON* l = cJSON_GetObjectItem(root, "led"); cJSON_IsObject(l)) {
            if (!GetInt(l, "brightness", led.brightness, 1, 100, error) ||
                !GetRgb(l, "idle", led.idle, error) || !GetRgb(l, "listening", led.listening, error) ||
                !GetRgb(l, "speaking", led.speaking, error) || !GetRgb(l, "connecting", led.connecting, error) ||
                !GetRgb(l, "starting", led.starting, error) || !GetRgb(l, "activating", led.activating, error) ||
                !GetRgb(l, "upgrading", led.upgrading, error)) {
                return false;
            }
            if (cJSON* moods = cJSON_GetObjectItem(l, "moods"); cJSON_IsObject(moods)) {
                for (cJSON* item = moods->child; item != nullptr; item = item->next) {
                    Rgb rgb = led.moods.count(item->string) ? led.moods[item->string] : Rgb();
                    if (strlen(item->string) > 24 || led.moods.size() > 40 || !GetRgb(moods, item->string, rgb, error)) {
                        if (error.empty()) {
                            error = std::string("led.moods.") + item->string + " khong hop le";
                        }
                        return false;
                    }
                    led.moods[item->string] = rgb;
                }
            }
        }
        if (cJSON* t = cJSON_GetObjectItem(root, "mcp_tools"); cJSON_IsObject(t)) {
            for (cJSON* item = t->child; item != nullptr; item = item->next) {
                auto found = tools.find(item->string);
                if (found == tools.end()) {
                    continue;  // unknown tool name: ignore
                }
                if (!cJSON_IsObject(item)) {
                    error = std::string("mcp_tools.") + item->string + " khong hop le";
                    return false;
                }
                Tool& tool = found->second;
                if (!GetBool(item, "enabled", tool.enabled, error) ||
                    !GetString(item, "description", tool.description, 300, error)) {
                    return false;
                }
                if (cJSON_GetObjectItem(item, "speed") != nullptr) {
                    int speed = tool.speed;
                    if (!GetInt(item, "speed", speed, 30, 100, error)) {
                        return false;
                    }
                    tool.speed = speed;
                }
                if (cJSON_GetObjectItem(item, "duration_ms") != nullptr) {
                    int duration = tool.duration_ms;
                    if (!GetInt(item, "duration_ms", duration, 100, 10000, error)) {
                        return false;
                    }
                    tool.duration_ms = duration;
                }
            }
        }
        return true;
    }
};

#endif // __ROBOT_CONFIG_H__
