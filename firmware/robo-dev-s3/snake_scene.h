#pragma once

#include <lvgl.h>

#include <esp_random.h>

#include <cstring>

// Idle screen: a snake that plays itself, like the demo screen of the classic Snake game.
// It heads for the food by the shortest free path, grows when it eats, and starts over when it
// has nowhere left to go or gets very long.
class SnakeScene {
public:
    lv_obj_t* root() const { return root_; }

    // Must be called with the display lock held.
    void Create(lv_obj_t* screen) {
        root_ = lv_obj_create(screen);
        lv_obj_set_size(root_, LV_HOR_RES, LV_VER_RES);
        lv_obj_set_pos(root_, 0, 0);
        Style(root_, 0x000000);

        for (int i = 0; i < kMaxLen; i++) {
            cells_[i] = lv_obj_create(root_);
            lv_obj_set_size(cells_[i], kCell - 1, kCell - 1);
            Style(cells_[i], 0x00C853);
            lv_obj_add_flag(cells_[i], LV_OBJ_FLAG_HIDDEN);
        }
        food_ = lv_obj_create(root_);
        lv_obj_set_size(food_, kCell - 3, kCell - 3);
        Style(food_, 0xFF5252);
        lv_obj_set_style_radius(food_, kCell, 0);

        Reset();
        timer_ = lv_timer_create([](lv_timer_t* t) {
            static_cast<SnakeScene*>(lv_timer_get_user_data(t))->Step();
        }, kStepMs, this);
    }

private:
    static constexpr int kCell = 12;
    static constexpr int kGrid = 20;  // 20 x 20 cells of 12 px = the 240 x 240 screen
    static constexpr int kMaxLen = 60;
    static constexpr uint32_t kStepMs = 110;
    static constexpr int kNoPath = 1000;

    lv_obj_t* root_ = nullptr;
    lv_obj_t* cells_[kMaxLen] = {};
    lv_obj_t* food_ = nullptr;
    lv_timer_t* timer_ = nullptr;
    int body_[kMaxLen] = {};  // cell index (y * kGrid + x); body_[0] is the head
    int len_ = 0;
    int food_cell_ = 0;
    int pause_ = 0;
    int ticks_ = 0;

    static void Style(lv_obj_t* o, uint32_t color) {
        lv_obj_set_style_bg_color(o, lv_color_hex(color), 0);
        lv_obj_set_style_bg_opa(o, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(o, 2, 0);
        lv_obj_set_style_border_width(o, 0, 0);
        lv_obj_set_style_outline_width(o, 0, 0);
        lv_obj_set_style_shadow_width(o, 0, 0);
        lv_obj_set_style_pad_all(o, 0, 0);
        lv_obj_remove_flag(o, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_remove_flag(o, LV_OBJ_FLAG_CLICKABLE);
    }

    void Reset() {
        len_ = 3;
        for (int i = 0; i < len_; i++) {
            body_[i] = (kGrid / 2) * kGrid + 5 - i;
        }
        PlaceFood();
        pause_ = 0;
        Render();
    }

    bool Occupied(int cell) const {
        for (int i = 0; i < len_; i++) {
            if (body_[i] == cell) {
                return true;
            }
        }
        return false;
    }

    void PlaceFood() {
        int free_cells = kGrid * kGrid - len_;
        int pick = esp_random() % free_cells;
        for (int c = 0; c < kGrid * kGrid; c++) {
            if (!Occupied(c) && pick-- == 0) {
                food_cell_ = c;
                return;
            }
        }
    }

    // Neighbour of `cell` in direction d (0 up, 1 right, 2 down, 3 left); -1 outside the grid.
    static int Neighbour(int cell, int d) {
        int x = cell % kGrid, y = cell / kGrid;
        switch (d) {
        case 0: y--; break;
        case 1: x++; break;
        case 2: y++; break;
        default: x--; break;
        }
        return (x < 0 || y < 0 || x >= kGrid || y >= kGrid) ? -1 : y * kGrid + x;
    }

    // Distance of every cell from `from` over free cells (the tail cell counts as free: it moves
    // away). Returns how many cells were reached.
    int Flood(int from, int* dist) const {
        bool blocked[kGrid * kGrid] = {};
        for (int i = 0; i < len_ - 1; i++) {
            blocked[body_[i]] = true;
        }
        for (int i = 0; i < kGrid * kGrid; i++) {
            dist[i] = kNoPath;
        }
        int queue[kGrid * kGrid];
        int head = 0, tail = 0;
        dist[from] = 0;
        queue[tail++] = from;
        while (head < tail) {
            int c = queue[head++];
            for (int d = 0; d < 4; d++) {
                int n = Neighbour(c, d);
                if (n >= 0 && !blocked[n] && dist[n] == kNoPath) {
                    dist[n] = dist[c] + 1;
                    queue[tail++] = n;
                }
            }
        }
        return tail;
    }

    // Picks the next head cell, or -1 when the snake is trapped.
    int ChooseMove() const {
        int dist[kGrid * kGrid];
        Flood(food_cell_, dist);
        int best = -1, best_dist = kNoPath;
        for (int d = 0; d < 4; d++) {
            int n = Neighbour(body_[0], d);
            if (n < 0 || (Occupied(n) && n != body_[len_ - 1])) {
                continue;
            }
            if (dist[n] < best_dist) {
                best_dist = dist[n];
                best = n;
            }
        }
        if (best >= 0) {
            return best;
        }
        // No way to the food: head for the neighbour with the most room around it
        int best_room = -1;
        for (int d = 0; d < 4; d++) {
            int n = Neighbour(body_[0], d);
            if (n < 0 || (Occupied(n) && n != body_[len_ - 1])) {
                continue;
            }
            int room = Flood(n, dist);
            if (room > best_room) {
                best_room = room;
                best = n;
            }
        }
        return best;
    }

    void Step() {
        ticks_++;
        if (pause_ > 0) {
            if (--pause_ == 0) {
                Reset();
            }
            return;
        }
        int next = ChooseMove();
        if (next < 0 || len_ >= kMaxLen - 1) {
            pause_ = 8;  // game over: hold the picture for a moment, then start again
            return;
        }
        bool eat = next == food_cell_;
        if (eat) {
            len_++;
        }
        for (int i = len_ - 1; i > 0; i--) {
            body_[i] = body_[i - 1];
        }
        body_[0] = next;
        if (eat) {
            PlaceFood();
        }
        Render();
    }

    void Render() {
        for (int i = 0; i < kMaxLen; i++) {
            if (i >= len_) {
                lv_obj_add_flag(cells_[i], LV_OBJ_FLAG_HIDDEN);
                continue;
            }
            lv_obj_remove_flag(cells_[i], LV_OBJ_FLAG_HIDDEN);
            lv_obj_set_pos(cells_[i], (body_[i] % kGrid) * kCell, (body_[i] / kGrid) * kCell);
            // Bright head, body fading towards the tail
            uint8_t g = i == 0 ? 0xFF : (uint8_t)(0xD0 - (0x90 * i) / len_);
            lv_obj_set_style_bg_color(cells_[i], lv_color_make(i == 0 ? 0xB9 : 0x00, g, i == 0 ? 0x6C : 0x30), 0);
        }
        lv_obj_set_pos(food_, (food_cell_ % kGrid) * kCell + 1, (food_cell_ / kGrid) * kCell + 1);
    }
};
