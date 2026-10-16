"""Kiểm tra cách gán chân GPIO của hồ sơ. Firmware Robo Dev kiểm tra lại đúng các luật này khi khởi động."""
from dataclasses import dataclass

from robodev.core import catalog

UNUSED = -1


@dataclass(frozen=True)
class Issue:
    level: str        # "error" | "warning"
    module: str
    signal: str | None
    gpio: int | None
    text: str


def assignments(hw):
    """[(module_key, signal_key, gpio)] của các module đang bật, bỏ qua chân "không dùng"."""
    out = []
    for mod in catalog.modules():
        entry = hw.get(mod.key, {})
        if mod.optional and not entry.get("enabled", True):
            continue
        for sig in mod.signals:
            gpio = entry.get(sig.key, UNUSED)
            if isinstance(gpio, int) and gpio != UNUSED:
                out.append((mod.key, sig.key, gpio))
    return out


def validate(hw):
    """Danh sách lỗi và cảnh báo, lỗi lên trước."""
    board = catalog.board()
    variant = hw.get("variant", "usb")
    header = set(board.header_gpios)
    issues = []
    used = {}

    for mod in catalog.modules():
        entry = hw.get(mod.key, {})
        if mod.optional and not entry.get("enabled", True):
            continue
        for sig in mod.signals:
            gpio = entry.get(sig.key, UNUSED)
            if gpio in (None, UNUSED):
                if not sig.optional:
                    issues.append(Issue("error", mod.key, sig.key, None,
                                        f"{mod.name}: chưa chọn chân cho {sig.label}."))
                continue
            if not isinstance(gpio, int) or gpio not in header:
                issues.append(Issue("error", mod.key, sig.key, gpio if isinstance(gpio, int) else None,
                                    f"{mod.name} {sig.label}: GPIO{gpio} không có chân cắm trên mạch này."))
            used.setdefault(gpio, []).append((mod, sig))

    for gpio, users in used.items():
        if len(users) > 1:
            names = ", ".join(f"{m.name} {s.label}" for m, s in users)
            for mod, sig in users:
                issues.append(Issue("error", mod.key, sig.key, gpio,
                                    f"GPIO{gpio} đang bị dùng cho nhiều tín hiệu: {names}. Mỗi chân chỉ nối một dây."))
        for mod, sig in users:
            for rule in board.rules_for(gpio, variant, mod.key):
                issues.append(Issue(rule.level, mod.key, sig.key, gpio,
                                    f"{mod.name} {sig.label}: " + rule.text.format(gpio=gpio)))

    issues.sort(key=lambda i: (i.level != "error", i.module, i.signal or ""))
    return issues


def pin_state(gpio, hw):
    """Trạng thái một chân để tô màu trên hình mạch: (kind, chi tiết).

    kind: "used" | "conflict" | "blocked" | "caution" | "free"
    """
    board = catalog.board()
    variant = hw.get("variant", "usb")
    users = [(m, s) for m, s, g in assignments(hw) if g == gpio]
    if len(users) > 1:
        return "conflict", users
    if users:
        mod_key = users[0][0]
        rules = board.rules_for(gpio, variant, mod_key)
        if any(r.level == "error" for r in rules):
            return "conflict", users
        return "used", users
    rules = board.rules_for(gpio, variant)
    if any(r.level == "error" for r in rules):
        return "blocked", [r.text.format(gpio=gpio) for r in rules]
    if rules:
        return "caution", [r.text.format(gpio=gpio) for r in rules]
    return "free", []


def choice_hint(gpio, hw, module_key):
    """Mức độ khi chọn `gpio` cho `module_key`: None (ổn), "warning" hoặc "error"."""
    board = catalog.board()
    rules = board.rules_for(gpio, hw.get("variant", "usb"), module_key)
    if any(r.level == "error" for r in rules):
        return "error"
    if rules:
        return "warning"
    return None
