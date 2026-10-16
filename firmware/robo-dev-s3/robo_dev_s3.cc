#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/lcd_display.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "robot_motor_controller.h"
#include "vl6180x.h"
#include "robot_behavior.h"
#include "robot_led.h"
#include "alarm_chime.h"
#include "serial_setup.h"
#include "robot_config.h"
#include "robot_weather.h"
#include "snake_scene.h"
#include "settings.h"
#include "assets/lang_config.h"
#include "mcp_server.h"

#include <functional>
#include <ctime>
#include <cstdio>
#include <cstring>

#include <esp_netif.h>
#include <esp_timer.h>
#include <esp_wifi.h>

#include <esp_log.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <driver/spi_common.h>
#include <driver/i2c_master.h>
#include <driver/gpio.h>

#define TAG "RoboDevS3"

// Face display that also reports every emotion, so the robot can move and glow with it.
// The idle screen is a self-playing Snake game; ShowDetails() covers it for a few seconds with a status
// panel (Wi-Fi signal, battery, time, weather), and the snake comes back by themselves.
class RobotDisplay : public SpiLcdDisplay {
public:
    using SpiLcdDisplay::SpiLcdDisplay;

    void OnEmotion(std::function<void(const char*)> callback) { on_emotion_ = std::move(callback); }

    void SetEmotion(const char* emotion) override {
        SpiLcdDisplay::SetEmotion(emotion);
        if (on_emotion_) {
            on_emotion_(emotion);
        }
    }

    void SetupUI() override {
        SpiLcdDisplay::SetupUI();
        // Only the face is shown; subtitles may contain glyphs the built-in font lacks
        if (RobotConfig::Get().features.hide_subtitle) {
            SetHideSubtitle(true);
        }
        CreateSnakeScene();
        CreateDetailsPanel();
        CreateDistancePanel();
        Settings settings("rd_screen", false);
        SetStatusBarVisible(settings.GetBool("status_bar", true), false);
    }

    // Status text / Wi-Fi icon bar. When it is hidden, listening and speaking are shown by the eyes.
    void SetStatusBarVisible(bool visible, bool save = true) {
        status_bar_visible_ = visible;
        if (top_bar_ != nullptr) {
            DisplayLockGuard lock(this);
            if (visible) {
                lv_obj_remove_flag(top_bar_, LV_OBJ_FLAG_HIDDEN);
            } else {
                lv_obj_add_flag(top_bar_, LV_OBJ_FLAG_HIDDEN);
            }
        }
        if (save) {
            Settings settings("rd_screen", true);
            settings.SetBool("status_bar", visible);
        }
    }

    void SetStatus(const char* status) override {
        SpiLcdDisplay::SetStatus(status);
        if (status_bar_visible_ || status == nullptr) {
            return;
        }
        // Eyes only (no motion): thinking eyes while listening, confident eyes while speaking
        if (strcmp(status, Lang::Strings::LISTENING) == 0) {
            SpiLcdDisplay::SetEmotion("thinking");
        } else if (strcmp(status, Lang::Strings::SPEAKING) == 0) {
            SpiLcdDisplay::SetEmotion("confident");
        }
    }

    void SetPanel(esp_lcd_panel_handle_t panel) { panel_handle_ = panel; }

    // Distance in mm (-1 = nothing in range), and whether the sensor works at all.
    void SetDistanceSource(std::function<int()> source, bool sensor_ready) {
        distance_source_ = std::move(source);
        sensor_ready_ = sensor_ready;
    }

    // Distance mode: the screen shows the distance to the obstacle until it is switched off.
    void SetDistanceMode(bool on) {
        if (dist_panel_ == nullptr) {
            return;
        }
        if (on) {
            UpdateDistance();
            DisplayLockGuard lock(this);
            lv_obj_remove_flag(dist_panel_, LV_OBJ_FLAG_HIDDEN);
            lv_obj_move_foreground(dist_panel_);
            if (dist_timer_ != nullptr && !esp_timer_is_active(dist_timer_)) {
                esp_timer_start_periodic(dist_timer_, 200000);
            }
        } else {
            if (dist_timer_ != nullptr && esp_timer_is_active(dist_timer_)) {
                esp_timer_stop(dist_timer_);
            }
            DisplayLockGuard lock(this);
            lv_obj_add_flag(dist_panel_, LV_OBJ_FLAG_HIDDEN);
        }
    }

    // degrees: 0, 90, 180 or 270 (clockwise). The panel scans the memory in the new direction.
    bool SetRotation(int degrees, bool save = true) {
        bool swap_xy, mirror_x, mirror_y;
        switch (degrees) {
            case 0:   swap_xy = false; mirror_x = false; mirror_y = false; break;
            case 90:  swap_xy = true;  mirror_x = true;  mirror_y = false; break;
            case 180: swap_xy = false; mirror_x = true;  mirror_y = true;  break;
            case 270: swap_xy = true;  mirror_x = false; mirror_y = true;  break;
            default: return false;
        }
        if (panel_handle_ == nullptr) {
            return false;
        }
        {
            DisplayLockGuard lock(this);
            esp_lcd_panel_swap_xy(panel_handle_, swap_xy);
            esp_lcd_panel_mirror(panel_handle_, mirror_x, mirror_y);
            lv_obj_invalidate(lv_screen_active());  // redraw the whole screen in the new direction
        }
        if (save) {
            Settings settings("rd_screen", true);
            settings.SetInt("rotation", degrees);
        }
        return true;
    }

    // Shows the status panel for `seconds` (1-60), then goes back to the eyes.
    void ShowDetails(int seconds) {
        if (panel_ == nullptr) {
            return;
        }
        seconds = seconds < 1 ? 1 : (seconds > 60 ? 60 : seconds);
        hide_at_us_ = esp_timer_get_time() + (int64_t)seconds * 1000000;
        RobotWeather::GetInstance().Refresh();
        UpdateDetails();
        DisplayLockGuard lock(this);
        lv_obj_remove_flag(panel_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(panel_);
    }

    // Screen check for the Robo Dev test page: red, green and blue bars (left to right) inside a white
    // frame, drawn above everything for `seconds` (1-15). Wrong colours show inverted colours or a swapped
    // RGB order; a missing white edge shows a wrong offset or mirror setting.
    void ShowTestPattern(int seconds) {
        seconds = seconds < 1 ? 1 : (seconds > 15 ? 15 : seconds);
        {
            DisplayLockGuard lock(this);
            if (test_overlay_ == nullptr) {
                test_overlay_ = lv_obj_create(lv_layer_top());
                lv_obj_remove_style_all(test_overlay_);
                lv_obj_set_size(test_overlay_, LV_HOR_RES, LV_VER_RES);
                lv_obj_set_pos(test_overlay_, 0, 0);
                lv_obj_set_style_bg_color(test_overlay_, lv_color_white(), 0);
                lv_obj_set_style_bg_opa(test_overlay_, LV_OPA_COVER, 0);
                lv_obj_set_style_pad_all(test_overlay_, 8, 0);   // white frame around the bars
                lv_obj_set_style_pad_column(test_overlay_, 0, 0);
                lv_obj_set_flex_flow(test_overlay_, LV_FLEX_FLOW_ROW);
                lv_obj_remove_flag(test_overlay_, LV_OBJ_FLAG_SCROLLABLE);
                for (uint32_t color : {0xFF0000u, 0x00FF00u, 0x0000FFu}) {
                    lv_obj_t* bar = lv_obj_create(test_overlay_);
                    lv_obj_remove_style_all(bar);
                    lv_obj_set_flex_grow(bar, 1);
                    lv_obj_set_height(bar, LV_PCT(100));
                    lv_obj_set_style_bg_color(bar, lv_color_hex(color), 0);
                    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
                }
            }
            lv_obj_remove_flag(test_overlay_, LV_OBJ_FLAG_HIDDEN);
            lv_obj_move_foreground(test_overlay_);
        }
        if (test_timer_ == nullptr) {
            esp_timer_create_args_t args = {};
            args.callback = [](void* arg) {
                auto self = static_cast<RobotDisplay*>(arg);
                DisplayLockGuard lock(self);
                lv_obj_add_flag(self->test_overlay_, LV_OBJ_FLAG_HIDDEN);
            };
            args.arg = this;
            args.name = "rd_lcd_test";
            esp_timer_create(&args, &test_timer_);
        }
        if (test_timer_ != nullptr) {
            esp_timer_stop(test_timer_);
            esp_timer_start_once(test_timer_, (uint64_t)seconds * 1000000);
        }
    }

private:
    std::function<void(const char*)> on_emotion_;
    lv_obj_t* test_overlay_ = nullptr;
    esp_timer_handle_t test_timer_ = nullptr;
    lv_obj_t* panel_ = nullptr;
    lv_obj_t* dist_panel_ = nullptr;
    lv_obj_t* dist_title_ = nullptr;
    lv_obj_t* dist_value_ = nullptr;
    lv_obj_t* dist_unit_ = nullptr;
    esp_timer_handle_t dist_timer_ = nullptr;
    std::function<int()> distance_source_;
    bool sensor_ready_ = false;
    esp_lcd_panel_handle_t panel_handle_ = nullptr;
    bool status_bar_visible_ = true;
    lv_obj_t* time_label_ = nullptr;
    lv_obj_t* wifi_label_ = nullptr;
    lv_obj_t* battery_label_ = nullptr;
    lv_obj_t* weather_label_ = nullptr;
    esp_timer_handle_t timer_ = nullptr;
    volatile int64_t hide_at_us_ = 0;

    // The idle screen is a self-playing Snake game. It sits just above the eyes and below the status bars,
    // so the eyes are still updated underneath but never seen.
    void CreateSnakeScene() {
        DisplayLockGuard lock(this);
        scene_.Create(lv_screen_active());
        lv_obj_move_to_index(scene_.root(), emoji_box_ != nullptr ? lv_obj_get_index(emoji_box_) + 1 : 1);
    }

    SnakeScene scene_;

    lv_obj_t* AddLabel(lv_color_t color, const lv_font_t* font, int y) {
        lv_obj_t* label = lv_label_create(panel_);
        lv_obj_set_width(label, LV_HOR_RES - 16);
        lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_style_text_color(label, color, 0);
        if (font != nullptr) {
            lv_obj_set_style_text_font(label, font, 0);
        }
        lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
        lv_obj_align(label, LV_ALIGN_TOP_MID, 0, y);
        lv_label_set_text(label, "");
        return label;
    }

    void CreateDetailsPanel() {
        {
            DisplayLockGuard lock(this);
            panel_ = lv_obj_create(lv_screen_active());
            lv_obj_set_size(panel_, LV_HOR_RES, LV_VER_RES);
            lv_obj_set_pos(panel_, 0, 0);
            lv_obj_set_style_bg_color(panel_, lv_color_black(), 0);
            lv_obj_set_style_bg_opa(panel_, LV_OPA_COVER, 0);
            lv_obj_set_style_border_width(panel_, 0, 0);
            lv_obj_set_style_radius(panel_, 0, 0);
            lv_obj_set_style_pad_all(panel_, 0, 0);
            lv_obj_remove_flag(panel_, LV_OBJ_FLAG_SCROLLABLE);
            const lv_font_t* big = &lv_font_montserrat_48;
            time_label_ = AddLabel(lv_color_white(), big, 20);
            wifi_label_ = AddLabel(lv_color_hex(0x4FC3F7), nullptr, 100);
            battery_label_ = AddLabel(lv_color_hex(0x81C784), nullptr, 135);
            weather_label_ = AddLabel(lv_color_hex(0xFFD54F), nullptr, 170);
            lv_obj_add_flag(panel_, LV_OBJ_FLAG_HIDDEN);
        }
        esp_timer_create_args_t args = {};
        args.callback = [](void* arg) { static_cast<RobotDisplay*>(arg)->Tick(); };
        args.arg = this;
        args.name = "rd_details";
        if (esp_timer_create(&args, &timer_) == ESP_OK) {
            esp_timer_start_periodic(timer_, 1000000);
        }
    }

    void CreateDistancePanel() {
        {
            DisplayLockGuard lock(this);
            dist_panel_ = lv_obj_create(lv_screen_active());
            lv_obj_set_size(dist_panel_, LV_HOR_RES, LV_VER_RES);
            lv_obj_set_pos(dist_panel_, 0, 0);
            lv_obj_set_style_bg_color(dist_panel_, lv_color_black(), 0);
            lv_obj_set_style_bg_opa(dist_panel_, LV_OPA_COVER, 0);
            lv_obj_set_style_border_width(dist_panel_, 0, 0);
            lv_obj_set_style_radius(dist_panel_, 0, 0);
            lv_obj_set_style_pad_all(dist_panel_, 0, 0);
            lv_obj_remove_flag(dist_panel_, LV_OBJ_FLAG_SCROLLABLE);
            auto make = [this](const lv_font_t* font, int y) {
                lv_obj_t* label = lv_label_create(dist_panel_);
                lv_obj_set_width(label, LV_HOR_RES - 16);
                lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
                lv_obj_set_style_text_color(label, lv_color_white(), 0);
                if (font != nullptr) {
                    lv_obj_set_style_text_font(label, font, 0);
                }
                lv_obj_align(label, LV_ALIGN_TOP_MID, 0, y);
                lv_label_set_text(label, "");
                return label;
            };
            dist_title_ = make(nullptr, 24);
            dist_value_ = make(&lv_font_montserrat_48, 90);
            dist_unit_ = make(nullptr, 160);
            lv_label_set_text(dist_title_, "Do khoang cach");
            lv_obj_add_flag(dist_panel_, LV_OBJ_FLAG_HIDDEN);
        }
        esp_timer_create_args_t args = {};
        args.callback = [](void* arg) { static_cast<RobotDisplay*>(arg)->UpdateDistance(); };
        args.arg = this;
        args.name = "rd_distance";
        esp_timer_create(&args, &dist_timer_);
    }

    void UpdateDistance() {
        char value[16];
        const char* unit = "mm";
        lv_color_t color = lv_color_hex(0x81C784);
        if (!sensor_ready_) {
            snprintf(value, sizeof(value), "--");
            unit = "Khong co cam bien";
            color = lv_color_hex(0xE57373);
        } else {
            int mm = distance_source_ ? distance_source_() : -1;
            if (mm < 0 || mm >= Vl6180x::kMaxRangeMm) {
                snprintf(value, sizeof(value), "---");
                unit = "Khong thay vat can";
                color = lv_color_hex(0x9AA0A6);
            } else {
                snprintf(value, sizeof(value), "%d", mm);
                color = mm < 50 ? lv_color_hex(0xE57373) : (mm < 100 ? lv_color_hex(0xFFD54F) : lv_color_hex(0x81C784));
            }
        }
        DisplayLockGuard lock(this);
        lv_label_set_text(dist_value_, value);
        lv_label_set_text(dist_unit_, unit);
        lv_obj_set_style_text_color(dist_value_, color, 0);
    }

    void Tick() {
        if (hide_at_us_ == 0) {
            return;
        }
        if (esp_timer_get_time() >= hide_at_us_) {
            hide_at_us_ = 0;
            DisplayLockGuard lock(this);
            lv_obj_add_flag(panel_, LV_OBJ_FLAG_HIDDEN);
            return;
        }
        UpdateDetails();
    }

    void UpdateDetails() {
        char timestr[8] = "--:--";
        time_t now = time(nullptr);
        struct tm tm_now;
        localtime_r(&now, &tm_now);
        if (tm_now.tm_year >= 124) {  // clock was set from the server
            snprintf(timestr, sizeof(timestr), "%02d:%02d", tm_now.tm_hour, tm_now.tm_min);
        }

        char wifi[64] = "Wi-Fi: chua ket noi";
        wifi_ap_record_t ap = {};
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            snprintf(wifi, sizeof(wifi), "Wi-Fi: %.24s", (const char*)ap.ssid);
        }

        char battery[32] = "Pin: --";
        int level = 0;
        bool charging = false, discharging = false;
        if (Board::GetInstance().GetBatteryLevel(level, charging, discharging)) {
            snprintf(battery, sizeof(battery), "Pin: %d%%%s", level, charging ? " (sac)" : "");
        }

        std::string weather = RobotWeather::GetInstance().Text();
        DisplayLockGuard lock(this);
        lv_label_set_text(time_label_, timestr);
        lv_label_set_text(wifi_label_, wifi);
        lv_label_set_text(battery_label_, battery);
        lv_label_set_text(weather_label_, weather.c_str());
    }
};

class RoboDevS3 : public WifiBoard {
private:
    Button boot_button_;
    RobotDisplay* display_;
    RobotLed* led_ = nullptr;
    RobotBehavior* behavior_ = nullptr;
    RobotMotorController* motors_ = nullptr;
    Vl6180x distance_sensor_;
    volatile int distance_mm_ = Vl6180x::kOutOfRange;

    void InitializeSpi() {
        spi_bus_config_t buscfg = {};
        buscfg.mosi_io_num = DISPLAY_MOSI_PIN;
        buscfg.miso_io_num = GPIO_NUM_NC;
        buscfg.sclk_io_num = DISPLAY_CLK_PIN;
        buscfg.quadwp_io_num = GPIO_NUM_NC;
        buscfg.quadhd_io_num = GPIO_NUM_NC;
        buscfg.max_transfer_sz = DISPLAY_WIDTH * DISPLAY_HEIGHT * sizeof(uint16_t);
        ESP_ERROR_CHECK(spi_bus_initialize(SPI3_HOST, &buscfg, SPI_DMA_CH_AUTO));
    }

    void InitializeLcdDisplay() {
        esp_lcd_panel_io_handle_t panel_io = nullptr;
        esp_lcd_panel_handle_t panel = nullptr;
        ESP_LOGD(TAG, "Install panel IO");
        esp_lcd_panel_io_spi_config_t io_config = {};
        io_config.cs_gpio_num = DISPLAY_CS_PIN;
        io_config.dc_gpio_num = DISPLAY_DC_PIN;
        io_config.spi_mode = DISPLAY_SPI_MODE;
        io_config.pclk_hz = DISPLAY_SPI_CLOCK_HZ;
        io_config.trans_queue_depth = 10;
        io_config.lcd_cmd_bits = 8;
        io_config.lcd_param_bits = 8;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI3_HOST, &io_config, &panel_io));

        ESP_LOGD(TAG, "Install LCD driver");
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = DISPLAY_RST_PIN;
        panel_config.rgb_ele_order = DISPLAY_RGB_ORDER;
        panel_config.bits_per_pixel = 16;
        ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(panel_io, &panel_config, &panel));

        esp_lcd_panel_reset(panel);
        esp_lcd_panel_init(panel);
        esp_lcd_panel_invert_color(panel, DISPLAY_INVERT_COLOR);
        esp_lcd_panel_swap_xy(panel, DISPLAY_SWAP_XY);
        esp_lcd_panel_mirror(panel, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
        display_ = new RobotDisplay(panel_io, panel,
                                    DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_OFFSET_X, DISPLAY_OFFSET_Y,
                                    DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y, DISPLAY_SWAP_XY);
        display_->SetPanel(panel);
        Settings screen_settings("rd_screen", false);
        int rotation = screen_settings.GetInt("rotation", 0);
        if (rotation != 0) {
            display_->SetRotation(rotation, false);
        }
    }

    // Level of each pin with pull-up and with pull-down; a pin held LOW with the pull-up on is shorted or driven.
    void LogSensorPinLevels(const char* when) {
        // Reference pins (nothing connected) show what a floating pin reads on this board
        for (int pin : {(int)SENSOR_I2C_SDA_GPIO, (int)SENSOR_I2C_SCL_GPIO, 10, 11, 21, 47}) {
            gpio_config_t io = {};
            io.pin_bit_mask = 1ULL << pin;
            io.mode = GPIO_MODE_INPUT;
            io.pull_up_en = GPIO_PULLUP_ENABLE;
            gpio_config(&io);
            vTaskDelay(pdMS_TO_TICKS(5));
            int up = gpio_get_level((gpio_num_t)pin);
            io.pull_up_en = GPIO_PULLUP_DISABLE;
            io.pull_down_en = GPIO_PULLDOWN_ENABLE;
            gpio_config(&io);
            vTaskDelay(pdMS_TO_TICKS(5));
            int down = gpio_get_level((gpio_num_t)pin);
            ESP_LOGW(TAG, "[%s] GPIO%d: with pull-up=%d, with pull-down=%d (%s)", when, pin, up, down,
                     (up == 1 && down == 0) ? "floating, nothing drives it" :
                     (up == 0 && down == 0) ? "held LOW (short to GND or stuck device)" :
                     (up == 1 && down == 1) ? "held HIGH by the module" : "?");
            io.pull_down_en = GPIO_PULLDOWN_DISABLE;
            gpio_config(&io);
        }
    }

    // Logs what is on the sensor wires, scans the bus and tries SDA/SCL swapped, to find wiring faults.
    void DiagnoseSensorBus(i2c_master_bus_handle_t bus) {
        if (bus != nullptr) {
            int found = 0;
            for (int addr = 0x08; addr < 0x78; addr++) {
                if (i2c_master_probe(bus, addr, 20) == ESP_OK) {
                    ESP_LOGW(TAG, "I2C scan: device at 0x%02X", addr);
                    found++;
                }
            }
            ESP_LOGW(TAG, "I2C scan on SDA=%d SCL=%d: %d device(s)", (int)SENSOR_I2C_SDA_GPIO,
                     (int)SENSOR_I2C_SCL_GPIO, found);
            if (i2c_master_probe(bus, 0x29, 50) == ESP_OK) {
                // Identify what answers at 0x29 (VL53L0X: reg 0xC0=0xEE, VL53L1X: reg 0x010F=0xEACC, VL6180X: reg 0x0000=0xB4)
                i2c_master_dev_handle_t dev = nullptr;
                i2c_device_config_t dc = {};
                dc.dev_addr_length = I2C_ADDR_BIT_LEN_7;
                dc.device_address = 0x29;
                dc.scl_speed_hz = 100 * 1000;
                if (i2c_master_bus_add_device(bus, &dc, &dev) == ESP_OK) {
                    uint8_t r8 = 0xC0, v8 = 0xFF;
                    i2c_master_transmit_receive(dev, &r8, 1, &v8, 1, 100);
                    uint8_t r16[2] = {0x01, 0x0F}, v16[2] = {0xFF, 0xFF};
                    i2c_master_transmit_receive(dev, r16, 2, v16, 2, 100);
                    uint8_t r0[2] = {0x00, 0x00}, v0 = 0xFF;
                    i2c_master_transmit_receive(dev, r0, 2, &v0, 1, 100);
                    ESP_LOGW(TAG, "ID probe at 0x29: reg 0xC0=0x%02X, reg 0x010F=0x%02X%02X, reg 0x0000=0x%02X",
                             v8, v16[0], v16[1], v0);
                    i2c_master_bus_rm_device(dev);
                }
            }
            i2c_del_master_bus(bus);
        }
        i2c_master_bus_config_t swapped = {};
        swapped.i2c_port = I2C_NUM_0;
        swapped.sda_io_num = SENSOR_I2C_SCL_GPIO;
        swapped.scl_io_num = SENSOR_I2C_SDA_GPIO;
        swapped.clk_source = I2C_CLK_SRC_DEFAULT;
        swapped.glitch_ignore_cnt = 7;
        swapped.flags.enable_internal_pullup = 1;
        i2c_master_bus_handle_t bus2 = nullptr;
        if (i2c_new_master_bus(&swapped, &bus2) == ESP_OK) {
            if (i2c_master_probe(bus2, Vl6180x::kDefaultAddress, 100) == ESP_OK) {
                ESP_LOGW(TAG, "VL6180X answers with SDA and SCL SWAPPED: swap the two wires");
            }
            i2c_del_master_bus(bus2);
        }
    }

    void InitializeDistanceSensor() {
        LogSensorPinLevels("before I2C init");
        i2c_master_bus_config_t bus_config = {};
        bus_config.i2c_port = I2C_NUM_0;
        bus_config.sda_io_num = SENSOR_I2C_SDA_GPIO;
        bus_config.scl_io_num = SENSOR_I2C_SCL_GPIO;
        bus_config.clk_source = I2C_CLK_SRC_DEFAULT;
        bus_config.glitch_ignore_cnt = 7;
        bus_config.flags.enable_internal_pullup = 1;
        i2c_master_bus_handle_t bus = nullptr;
        if (i2c_new_master_bus(&bus_config, &bus) != ESP_OK ||
            !distance_sensor_.Init(bus)) {
            ESP_LOGW(TAG, "VL6180X not available, obstacle detection disabled");
            DiagnoseSensorBus(bus);
            return;
        }

        const auto& distance_tool = RobotConfig::Get().tools.at("get_distance");
        if (distance_tool.enabled) {
            McpServer::GetInstance().AddTool("self.robot.get_distance",
                distance_tool.description.empty()
                    ? "Get the distance in millimeters to the obstacle in front of the robot. "
                      "Returns -1 when nothing is detected within range."
                    : distance_tool.description,
                PropertyList(),
                [this](const PropertyList& properties) -> ReturnValue {
                    return (int)distance_mm_;
                });
        }

        xTaskCreate([](void* arg) {
            static_cast<RoboDevS3*>(arg)->DistanceTask();
        }, "distance", 3072, this, 3, nullptr);
    }

    // Measures continuously and stops the robot when it drives toward an obstacle.
    void DistanceTask() {
        while (true) {
            int mm = distance_sensor_.ReadRangeMm();
            distance_mm_ = mm;
            const auto& cfg = RobotConfig::Get();
            if (cfg.features.obstacle_stop && mm != Vl6180x::kOutOfRange &&
                mm < cfg.obstacle.stop_distance_mm && motors_ && motors_->IsMovingForward()) {
                motors_->Stop();
                if (behavior_ != nullptr) {
                    behavior_->OnObstacle(mm);
                }
            }
            vTaskDelay(pdMS_TO_TICKS(50));
        }
    }

    void InitializeButtons() {
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });
    }

public:
    RoboDevS3() : boot_button_(BOOT_BUTTON_GPIO) {
        // The default >>12 clips the INMP441 (full-scale noise, AI hears garbage); >>15 keeps speech in range
        NoAudioCodec::input_shift = 15;
        InitializeSpi();
        InitializeLcdDisplay();
        InitializeButtons();
#if ROBOT_ENABLE_MOTORS
        if (RobotConfig::Get().features.motors) {
            motors_ = new RobotMotorController(MOTOR_A_IN1_GPIO, MOTOR_A_IN2_GPIO,
                                               MOTOR_B_IN3_GPIO, MOTOR_B_IN4_GPIO);
        }
#endif
        InitializeDistanceSensor();
        if (RobotConfig::Get().features.led) {
            led_ = new RobotLed(BUILTIN_LED_GPIO);
        }
        auto serial = new SerialSetup([this]() { return distance_sensor_.ready(); }, [this]() { return (int)distance_mm_; });
        serial->SetLcdTest([this](int seconds) {
            if (display_ == nullptr) {
                return false;
            }
            display_->ShowTestPattern(seconds);
            return true;
        });
        AlarmChime::GetInstance().Start();        if (motors_ != nullptr) {
            behavior_ = new RobotBehavior(motors_, [this]() { return (int)distance_mm_; },
                                        distance_sensor_.ready());
        }
        McpServer::GetInstance().AddTool("self.screen.set_rotation",
            "Rotate the screen picture. degrees is 0 (normal), 90, 180 (upside down) or 270, clockwise. "
            "Call this when the user asks to turn, rotate or flip the screen. The setting is remembered.",
            PropertyList({Property("degrees", kPropertyTypeInteger, 0, 0, 270)}),
            [this](const PropertyList& properties) -> ReturnValue {
                int degrees = properties["degrees"].value<int>();
                if (!display_->SetRotation(degrees)) {
                    return std::string("error: degrees must be 0, 90, 180 or 270");
                }
                return true;
            });
        McpServer::GetInstance().AddTool("self.screen.set_status_bar",
            "Show or hide the top bar of the screen (Wi-Fi icon and the status text such as listening or "
            "speaking). When hidden, listening and speaking are shown by the robot eyes instead. "
            "Call this when the user asks to hide or show the Wi-Fi info or the status text. Remembered.",
            PropertyList({Property("visible", kPropertyTypeBoolean)}),
            [this](const PropertyList& properties) -> ReturnValue {
                display_->SetStatusBarVisible(properties["visible"].value<bool>());
                return true;
            });
        display_->SetDistanceSource([this]() { return (int)distance_mm_; }, distance_sensor_.ready());
        McpServer::GetInstance().AddTool("self.screen.distance_mode",
            "Switch the screen to distance measuring mode (enabled=true): it shows the distance in millimeters "
            "from the robot to the obstacle in front, updated live. Call this when the user asks the robot to "
            "measure distance or switch to distance mode. Call with enabled=false to go back to the robot eyes.",
            PropertyList({Property("enabled", kPropertyTypeBoolean)}),
            [this](const PropertyList& properties) -> ReturnValue {
                display_->SetDistanceMode(properties["enabled"].value<bool>());
                return true;
            });
        McpServer::GetInstance().AddTool("self.screen.show_details",
            "Show the device details on the screen for a few seconds: Wi-Fi signal, battery percentage, "
            "current time and weather. Call this when the user asks to see the configuration, status, "
            "details, time or weather on the screen. The screen goes back to the robot eyes by itself.",
            PropertyList({Property("seconds", kPropertyTypeInteger, 10, 1, 60)}),
            [this](const PropertyList& properties) -> ReturnValue {
                display_->ShowDetails(properties["seconds"].value<int>());
                return true;
            });
        display_->OnEmotion([this](const char* emotion) {
            if (led_ != nullptr) {
                led_->SetEmotion(emotion);
            }
            if (behavior_ != nullptr) {
                behavior_->OnEmotion(emotion);
            }
        });
    }

    virtual AudioCodec* GetAudioCodec() override {
        static NoAudioCodecSimplex audio_codec(AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK, AUDIO_I2S_SPK_GPIO_LRCK, AUDIO_I2S_SPK_GPIO_DOUT, I2S_STD_SLOT_LEFT,
            AUDIO_I2S_MIC_GPIO_SCK, AUDIO_I2S_MIC_GPIO_WS, AUDIO_I2S_MIC_GPIO_DIN, I2S_STD_SLOT_RIGHT);
        return &audio_codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }

    virtual Led* GetLed() override {
        return led_ != nullptr ? static_cast<Led*>(led_) : Board::GetLed();
    }
};

DECLARE_BOARD(RoboDevS3);
