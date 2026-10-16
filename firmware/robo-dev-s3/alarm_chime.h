#ifndef __ALARM_CHIME_H__
#define __ALARM_CHIME_H__

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <string>
#include <vector>

#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "application.h"
#include "board.h"
#include "settings.h"

// Chime mode: every 30 minutes (at :00 and :30) the board plays a short classical piece, then waits
// for the next slot. All pieces are public domain (composers died long before 1955) and are
// synthesised from note tables, so no audio files are stored.
//
// The clock comes from the server time received when the board starts (already shifted to local
// time), so nothing rings until the board has been online once. The chime is skipped while the AI is
// talking or listening.
//
// Settings (namespace "alarm"): enabled (default 1), quiet_from / quiet_to (hours; equal = no quiet period).
namespace alarm_chime {

struct Note {
    uint8_t midi;   // MIDI note number, 0 = rest
    uint8_t units;  // length in units of Piece::unit_ms
};

struct Piece {
    const char* name;
    int unit_ms;
    const Note* notes;
    size_t count;
};

// Beethoven - Fur Elise (1810)
inline constexpr Note kFurElise[] = {
    {76, 1}, {75, 1}, {76, 1}, {75, 1}, {76, 1}, {71, 1}, {74, 1}, {72, 1}, {69, 3}, {0, 1},
    {60, 1}, {64, 1}, {69, 1}, {71, 3}, {0, 1}, {64, 1}, {68, 1}, {71, 1}, {72, 3}, {0, 1},
    {76, 1}, {75, 1}, {76, 1}, {75, 1}, {76, 1}, {71, 1}, {74, 1}, {72, 1}, {69, 6},
};
// Beethoven - Ode to Joy (1824)
inline constexpr Note kOdeToJoy[] = {
    {64, 2}, {64, 2}, {65, 2}, {67, 2}, {67, 2}, {65, 2}, {64, 2}, {62, 2},
    {60, 2}, {60, 2}, {62, 2}, {64, 2}, {64, 3}, {62, 1}, {62, 4},
};
// Westminster Quarters (1793)
inline constexpr Note kWestminster[] = {
    {68, 1}, {66, 1}, {64, 1}, {59, 2}, {0, 1}, {64, 1}, {68, 1}, {66, 1}, {59, 2}, {0, 1},
    {64, 1}, {66, 1}, {68, 1}, {64, 3},
};
// Petzold / Bach notebook - Minuet in G (c. 1725)
inline constexpr Note kMinuetInG[] = {
    {74, 2}, {67, 1}, {69, 1}, {71, 1}, {72, 1}, {74, 2}, {67, 2}, {67, 2},
    {76, 2}, {72, 1}, {74, 1}, {76, 1}, {78, 1}, {79, 2}, {67, 2}, {67, 2},
};
// Mozart - Eine kleine Nachtmusik (1787)
inline constexpr Note kNachtmusik[] = {
    {67, 2}, {62, 1}, {67, 2}, {62, 1}, {67, 2}, {62, 1}, {67, 1}, {71, 1}, {74, 4}, {0, 1},
    {72, 2}, {69, 1}, {72, 2}, {69, 1}, {72, 2}, {69, 1}, {66, 1}, {69, 1}, {74, 4},
};
// Grieg - Morning Mood, Peer Gynt (1875)
inline constexpr Note kMorningMood[] = {
    {76, 3}, {74, 3}, {71, 3}, {69, 3}, {71, 3}, {74, 3}, {76, 3}, {74, 3},
    {71, 3}, {69, 3}, {71, 3}, {74, 3}, {76, 3}, {74, 3}, {71, 3}, {69, 6},
};
// Pachelbel - Canon in D (c. 1680)
inline constexpr Note kCanon[] = {
    {78, 3}, {76, 3}, {74, 3}, {73, 3}, {71, 3}, {69, 3}, {71, 3}, {73, 3}, {74, 6},
};
// Brahms - Lullaby (1868)
inline constexpr Note kLullaby[] = {
    {67, 2}, {67, 2}, {71, 6}, {67, 2}, {67, 2}, {71, 6},
    {67, 2}, {71, 2}, {74, 4}, {72, 2}, {72, 2}, {71, 2}, {69, 6},
};

#define ALARM_PIECE(name, unit, arr) {name, unit, arr, sizeof(arr) / sizeof(arr[0])}
inline constexpr Piece kPieces[] = {
    ALARM_PIECE("Fur Elise", 130, kFurElise),
    ALARM_PIECE("Ode to Joy", 110, kOdeToJoy),
    ALARM_PIECE("Westminster", 330, kWestminster),
    ALARM_PIECE("Minuet in G", 120, kMinuetInG),
    ALARM_PIECE("Eine kleine Nachtmusik", 120, kNachtmusik),
    ALARM_PIECE("Morning Mood", 110, kMorningMood),
    ALARM_PIECE("Canon in D", 150, kCanon),
    ALARM_PIECE("Brahms Lullaby", 150, kLullaby),
};
#undef ALARM_PIECE
inline constexpr int kPieceCount = sizeof(kPieces) / sizeof(kPieces[0]);

}  // namespace alarm_chime

class AlarmChime {
public:
    static AlarmChime& GetInstance() {
        static AlarmChime instance;
        return instance;
    }

    void Start() {
        if (started_) {
            return;
        }
        started_ = true;
        xTaskCreate([](void*) { AlarmChime::GetInstance().Run(); }, "alarm_chime", 6144, nullptr, 2, nullptr);
    }

    bool enabled() { return Settings("alarm").GetInt("enabled", 1) != 0; }
    void SetEnabled(bool on) { Settings("alarm", true).SetInt("enabled", on ? 1 : 0); }
    int quiet_from() { return Settings("alarm").GetInt("quiet_from", 0); }
    int quiet_to() { return Settings("alarm").GetInt("quiet_to", 0); }
    void SetQuietHours(int from, int to) {
        Settings settings("alarm", true);
        settings.SetInt("quiet_from", std::clamp(from, 0, 23));
        settings.SetInt("quiet_to", std::clamp(to, 0, 23));
    }

    // Local time; false until the clock has been set from the server.
    static bool LocalTime(struct tm* out) {
        time_t now = time(nullptr);
        localtime_r(&now, out);
        return out->tm_year >= 125;  // 2025 or later
    }

    // Plays one piece in the background (index modulo the number of pieces).
    void PlayAsync(int index) {
        xTaskCreate([](void* arg) {
            AlarmChime::GetInstance().PlayPiece((int)(intptr_t)arg, true);
            vTaskDelete(nullptr);
        }, "alarm_play", 6144, (void*)(intptr_t)index, 2, nullptr);
    }

    // Blocking. Stops early when the AI starts a conversation (unless force is set).
    void PlayPiece(int index, bool force) {
        using namespace alarm_chime;
        if (playing_) {
            return;
        }
        playing_ = true;
        const Piece& piece = kPieces[((index % kPieceCount) + kPieceCount) % kPieceCount];
        ESP_LOGI(TAG, "Playing \"%s\"", piece.name);
        auto& app = Application::GetInstance();
        const int rate = Board::GetInstance().GetAudioCodec()->output_sample_rate();
        for (size_t i = 0; i < piece.count; i++) {
            if (!force && app.GetDeviceState() != kDeviceStateIdle) {
                break;
            }
            if (!app.GetAudioService().PlayPcm(Render(piece.notes[i], piece.unit_ms, rate))) {
                break;
            }
        }
        playing_ = false;
    }

private:
    static constexpr const char* TAG = "AlarmChime";
    bool started_ = false;
    volatile bool playing_ = false;

    bool InQuietHours(int hour) {
        int from = quiet_from(), to = quiet_to();
        if (from == to) {
            return false;
        }
        return from < to ? (hour >= from && hour < to) : (hour >= from || hour < to);
    }

    void Run() {
        int last_slot = -1;
        while (true) {
            vTaskDelay(pdMS_TO_TICKS(1000));
            struct tm tm;
            if (!LocalTime(&tm) || tm.tm_min % 30 != 0) {
                continue;
            }
            const int half = tm.tm_hour * 2 + tm.tm_min / 30;
            const int slot = tm.tm_yday * 48 + half;
            if (slot == last_slot || !enabled() || InQuietHours(tm.tm_hour)) {
                continue;
            }
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() != kDeviceStateIdle || !app.GetAudioService().IsPlaybackIdle()) {
                continue;  // retry for the rest of this minute
            }
            last_slot = slot;
            const int index = half % alarm_chime::kPieceCount;
            char text[64];
            snprintf(text, sizeof(text), "%02d:%02d - %s", tm.tm_hour, tm.tm_min, alarm_chime::kPieces[index].name);
            app.Schedule([text = std::string(text)]() {
                if (auto* display = Board::GetInstance().GetDisplay()) {
                    display->ShowNotification(text, 5000);
                }
            });
            PlayPiece(index, false);
        }
    }

    // One note as 16-bit mono PCM: a few soft overtones, fast attack, decay to a sustain and a short release.
    static std::vector<int16_t> Render(const alarm_chime::Note& note, int unit_ms, int rate) {
        const int total = note.units * unit_ms * rate / 1000;
        std::vector<int16_t> pcm(total, 0);
        if (note.midi == 0) {
            return pcm;
        }
        const float freq = 440.0f * powf(2.0f, (note.midi - 69) / 12.0f);
        const float w = 2.0f * (float)M_PI * freq / rate;
        const int attack = rate * 5 / 1000;
        const int release = std::min(total / 3, rate * 60 / 1000);
        const int gap = std::min(total / 6, rate * 25 / 1000);
        const int body = total - gap;
        for (int i = 0; i < body; i++) {
            float tone = sinf(w * i) + 0.35f * sinf(2 * w * i) + 0.12f * sinf(3 * w * i);
            float env = 0.35f + 0.65f * expf(-6.0f * i / rate);
            if (i < attack) {
                env *= (float)i / attack;
            }
            if (i > body - release) {
                env *= (float)(body - i) / release;
            }
            pcm[i] = (int16_t)(12000.0f * env * tone);
        }
        return pcm;
    }
};

#endif // __ALARM_CHIME_H__
