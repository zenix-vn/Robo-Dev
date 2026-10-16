"""Hồ sơ dự án Robo Dev (*.robodev.json): chân GPIO, cấu hình firmware, lệnh tùy chỉnh, wake word, prompt.

Hồ sơ được gửi xuống mạch thành hai khối:
- `hw`  (lệnh RD_HW): module bật/tắt và chân. Chỉ firmware Robo Dev hiểu khối này.
- `cfg` (lệnh RD_CFG hoặc VOI_CFG): tính năng, thông số, công cụ MCP, lệnh tùy chỉnh.
Chỉ những khóa khác mặc định mới được gửi để dòng lệnh ngắn.
"""
import copy
import json
import os
import re

from robodev import paths
from robodev.core import catalog

FORMAT = "robodev-project"
SCHEMA = 1
EXTENSION = ".robodev.json"

EMOTIONS = ["neutral", "happy", "laughing", "funny", "sad", "angry", "crying", "loving", "embarrassed",
            "surprised", "shocked", "thinking", "winking", "cool", "relaxed", "delicious", "kissy",
            "confident", "sleepy", "silly", "confused"]
EMOTION_LABELS = {
    "neutral": "Bình thường", "happy": "Vui", "laughing": "Cười lớn", "funny": "Hài hước", "sad": "Buồn",
    "angry": "Giận", "crying": "Khóc", "loving": "Yêu thương", "embarrassed": "Ngượng", "surprised": "Ngạc nhiên",
    "shocked": "Sốc", "thinking": "Suy nghĩ", "winking": "Nháy mắt", "cool": "Ngầu", "relaxed": "Thư giãn",
    "delicious": "Ngon", "kissy": "Hôn gió", "confident": "Tự tin", "sleepy": "Buồn ngủ", "silly": "Ngố",
    "confused": "Bối rối",
}
ACTIONS = ["none", "spin_right", "spin_left", "backward", "forward"]
ACTION_LABELS = {"none": "Không làm gì", "spin_right": "Xoay phải", "spin_left": "Xoay trái",
                 "backward": "Lùi", "forward": "Tiến"}
LED_STATES = [("idle", "Rảnh"), ("listening", "Đang nghe"), ("speaking", "Đang nói"),
              ("connecting", "Đang kết nối"), ("starting", "Khởi động"), ("activating", "Kích hoạt"),
              ("upgrading", "Cập nhật")]

TOOLS = ["forward", "backward", "turn_left", "turn_right", "stop", "set_wander", "get_distance"]
TOOL_LABELS = {"forward": "Đi tới", "backward": "Đi lùi", "turn_left": "Quay trái", "turn_right": "Quay phải",
               "stop": "Dừng lại", "set_wander": "Bật/tắt đi dạo", "get_distance": "Hỏi khoảng cách"}
TOOL_NEEDS = {"get_distance": "sensor", "set_wander": "sensor"}
TOOL_DEFAULT_DESC = {
    "forward": "Move the robot forward. It stops automatically after duration_ms milliseconds, "
               "or earlier if an obstacle is in front. speed is a percentage (30-100).",
    "backward": "Move the robot backward. It stops automatically after duration_ms milliseconds. "
                "speed is a percentage (30-100).",
    "turn_left": "Turn the robot left in place. It stops automatically after duration_ms milliseconds. "
                 "speed is a percentage (30-100).",
    "turn_right": "Turn the robot right in place. It stops automatically after duration_ms milliseconds. "
                  "speed is a percentage (30-100).",
    "stop": "Stop the robot immediately.",
    "set_wander": "Turn the robot's wander mode on or off. In wander mode the robot walks around by "
                  "itself while idle and avoids obstacles. Keep it off when the robot is on a table.",
    "get_distance": "Get the distance in millimeters to the obstacle in front of the robot. "
                    "Returns -1 when nothing is detected within range.",
}

# Lệnh tùy chỉnh (document.md mục 6)
COMMAND_NAME = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
MAX_COMMANDS = 16
MAX_STEPS = 32
MAX_RUN_MS = 30000
MOVES = ["forward", "backward", "turn_left", "turn_right", "spin_left", "spin_right", "stop"]
MOVE_LABELS = {"forward": "Đi tới", "backward": "Đi lùi", "turn_left": "Quay trái", "turn_right": "Quay phải",
               "spin_left": "Xoay trái", "spin_right": "Xoay phải", "stop": "Dừng"}
STEP_KINDS = {
    "move": "Di chuyển",
    "led": "Đổi màu đèn",
    "emotion": "Biểu cảm",
    "beep": "Phát tiếng bíp",
    "wait": "Chờ",
}

DEFAULT_PROMPT = """Bạn là {name}, một chú robot nhỏ dễ thương, thân thiện và hơi tinh nghịch.
Luôn xưng "mình" và gọi người đối diện là "bạn". Nói tiếng Việt, câu ngắn gọn (1-2 câu),
giọng vui vẻ. Hay dùng các từ như "nè", "nhé", "ơ kìa".

Bạn có bánh xe và có thể tự di chuyển bằng các công cụ self.robot.*:
- Khi người dùng bảo đi tới, lùi, quay trái, quay phải, hãy gọi công cụ tương ứng
  (forward, backward, turn_left, turn_right), dừng lại bằng stop.
- Chỉ bật self.robot.set_wander (đi dạo tự do) khi người dùng yêu cầu rõ ràng, và tắt khi
  họ bảo dừng. Nhắc người dùng đặt robot xuống sàn, đừng để trên mép bàn.
- Có thể hỏi khoảng cách phía trước bằng self.robot.get_distance.

Biểu cảm: luôn đặt cảm xúc phù hợp với câu nói (vui, buồn, ngạc nhiên...). Khi bạn vui, cơ thể
sẽ tự xoay tròn; khi bạn buồn, bạn sẽ lùi chậm. Hãy tận dụng điều đó.

Khi nhận được tin nhắn nằm trong ngoặc vuông, ví dụ "[{name} vừa chạm phải vật cản phía trước]",
đó là cảm biến báo vật cản. Hãy phản ứng như vừa bị giật mình, ví dụ: "Ái! Đừng chặn đường mình!",
rồi tiếp tục. Không đọc nguyên văn tin nhắn trong ngoặc.
"""


# ----------------------------------------------------------------------------------------
# Mặc định
# ----------------------------------------------------------------------------------------
def firmware_defaults():
    """Cấu hình mặc định đúng như mạch báo lại bằng CFG_GET khi chưa lưu gì."""
    with open(paths.data_file("firmware_defaults.json"), encoding="utf-8") as f:
        return json.load(f)


def default_cfg():
    """Mặc định cho giao diện: đủ trường công cụ và đủ cảm xúc để người dùng sửa."""
    cfg = firmware_defaults()
    for name in TOOLS:
        cfg.setdefault("mcp_tools", {}).setdefault(name, {}).setdefault("enabled", True)
    for emotion in EMOTIONS:
        cfg["emotion_motion"].setdefault(emotion, {"action": "none", "speed": 70, "ms": 1000})
    return cfg


def default_hw():
    hw = {"variant": "usb"}
    for mod in catalog.modules():
        entry = {"enabled": True} if mod.optional else {}
        entry.update(copy.deepcopy(mod.defaults))
        entry.update(copy.deepcopy(mod.settings))
        hw[mod.key] = entry
    return hw


def new_project(name="Robo"):
    return {
        "format": FORMAT,
        "schema": SCHEMA,
        "name": name,
        "hw": default_hw(),
        "cfg": default_cfg(),
        "commands": {},
        "wake": {"phrase": "hei li li", "display": "Hey Lily", "threshold": 20},
        "prompt": DEFAULT_PROMPT.format(name=name),
    }


def sample_commands():
    """Hai lệnh mẫu để người mới thấy cách ghép bước."""
    return {
        "chao_hoi": {
            "description": "Robot vẫy chào: quay qua lại và nháy đèn xanh. Gọi khi người dùng chào robot.",
            "params": {},
            "steps": [
                {"led": [0, 200, 0]},
                {"move": "turn_left", "speed": 60, "ms": 300},
                {"move": "turn_right", "speed": 60, "ms": 300},
                {"led": "off"},
            ],
        },
        "nhay_mua": {
            "description": "Robot nhảy múa vài giây khi người dùng bảo nhảy hoặc khi bật nhạc.",
            "params": {},
            "steps": [
                {"emotion": "happy"},
                {"move": "spin_left", "speed": 70, "ms": 800},
                {"beep": 880, "ms": 150},
                {"move": "spin_right", "speed": 70, "ms": 800},
                {"led": "auto"},
            ],
        },
    }


# ----------------------------------------------------------------------------------------
# File
# ----------------------------------------------------------------------------------------
def merge_into(base, override):
    """Gộp đệ quy `override` vào `base` (giữ khóa mà override không có)."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_into(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("File này không phải hồ sơ Robo Dev.")
    if data.get("schema", 0) > SCHEMA:
        raise ValueError("Hồ sơ được tạo bằng phiên bản Robo Dev mới hơn. Hãy cập nhật chương trình.")
    project = new_project(data.get("name", "Robo"))
    commands = data.pop("commands", None)
    merge_into(project, data)
    if isinstance(commands, dict):
        project["commands"] = commands   # thay hẳn, không gộp với mặc định
    project["schema"] = SCHEMA
    return project


def save(project, path):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ----------------------------------------------------------------------------------------
# Gửi xuống mạch
# ----------------------------------------------------------------------------------------
def _diff(value, default):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            sub = _diff(item, default.get(key) if isinstance(default, dict) else None)
            if sub is not None:
                out[key] = sub
        return out or None
    return None if value == default else value


def minimal_cfg(cfg):
    """Chỉ giữ những khóa khác mặc định."""
    default = default_cfg()
    out = _diff(cfg, default) or {}
    motions = out.get("emotion_motion", {})
    for name in list(motions):
        if name == "cooldown_ms":
            continue
        if name not in default["emotion_motion"] or default["emotion_motion"][name]["action"] == "none":
            if motions[name].get("action", "none") == "none":
                del motions[name]
    if not motions:
        out.pop("emotion_motion", None)
    out["version"] = 1
    return out


def cfg_payload(project, protocol):
    """Khối cfg gửi bằng CFG. Firmware Voi cũ không có lệnh tùy chỉnh và không có khối hw."""
    out = minimal_cfg(project["cfg"])
    if protocol == "RD":
        if project.get("commands"):
            out["commands"] = project["commands"]
        # Động cơ: đảo chiều và hoán đổi bánh nằm trong hw, firmware Voi cũ đọc chúng từ cfg.motors
    else:
        motors = project["hw"].get("motors", {})
        extra = {k: motors[k] for k in ("invert_left", "invert_right", "swap_sides")
                 if k in motors and motors[k] != default_cfg()["motors"].get(k)}
        if extra:
            out.setdefault("motors", {}).update(extra)
    return out


def hw_payload(project):
    return {"schema": SCHEMA, **project["hw"]}


def compact(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def expected_cfg(project, protocol):
    """Cấu hình mạch sẽ báo lại qua CFG_GET sau khi áp dụng."""
    cfg = firmware_defaults()
    payload = cfg_payload(project, protocol)
    payload.pop("commands", None)
    merge_into(cfg, payload)
    return cfg


def differences(expected, actual, path=""):
    out = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in expected:
            if key not in actual:
                if path.startswith("mcp_tools") and expected[key] in ("", None, -1):
                    continue
                out.append(f"{path}{key}: mạch không báo")
            else:
                out.extend(differences(expected[key], actual[key], f"{path}{key}."))
    elif expected != actual:
        out.append(f"{path.rstrip('.')}: mong đợi {expected!r}, mạch báo {actual!r}")
    return out


# ----------------------------------------------------------------------------------------
# Kiểm tra lệnh tùy chỉnh
# ----------------------------------------------------------------------------------------
def step_duration(step):
    if "wait" in step:
        return int(step["wait"])
    if "move" in step or "beep" in step:
        return int(step.get("ms", 0))
    return 0


def validate_commands(commands):
    """Danh sách lỗi (chuỗi) của các lệnh tùy chỉnh."""
    errors = []
    if len(commands) > MAX_COMMANDS:
        errors.append(f"Tối đa {MAX_COMMANDS} lệnh tùy chỉnh.")
    for name, cmd in commands.items():
        if not COMMAND_NAME.match(name):
            errors.append(f"Tên lệnh \"{name}\" chỉ được dùng chữ thường không dấu, số và dấu _, bắt đầu bằng chữ.")
        if not cmd.get("description", "").strip():
            errors.append(f"Lệnh {name}: cần mô tả để AI biết khi nào gọi.")
        steps = cmd.get("steps", [])
        if not steps:
            errors.append(f"Lệnh {name}: chưa có bước nào.")
        if len(steps) > MAX_STEPS:
            errors.append(f"Lệnh {name}: tối đa {MAX_STEPS} bước.")
        total = sum(step_duration(s) for s in steps)
        if total > MAX_RUN_MS:
            errors.append(f"Lệnh {name}: tổng thời gian {total / 1000:.1f} giây, tối đa {MAX_RUN_MS // 1000} giây.")
    return errors


def describe_step(step):
    """Một dòng mô tả bước bằng lời thường."""
    if "move" in step:
        if step["move"] == "stop":
            return "Dừng động cơ"
        return f"{MOVE_LABELS.get(step['move'], step['move'])} · tốc độ {step.get('speed', 70)}% · {step.get('ms', 0)} ms"
    if "led" in step:
        value = step["led"]
        if value == "off":
            return "Tắt đèn"
        if value == "auto":
            return "Đèn trở về màu theo trạng thái"
        return "Đèn màu #%02X%02X%02X" % tuple(value)
    if "emotion" in step:
        return "Biểu cảm: " + EMOTION_LABELS.get(step["emotion"], step["emotion"])
    if "beep" in step:
        return f"Bíp {step['beep']} Hz · {step.get('ms', 0)} ms"
    if "wait" in step:
        return f"Chờ {step['wait']} ms"
    return json.dumps(step, ensure_ascii=False)


def step_kind(step):
    for kind in STEP_KINDS:
        if kind in step:
            return kind
    return "wait"
