"""Danh mục board và module (đọc từ file dữ liệu trong robodev/data)."""
import json
from dataclasses import dataclass, field
from functools import lru_cache

from robodev import paths


@dataclass(frozen=True)
class Signal:
    key: str
    label: str
    optional: bool = False


@dataclass(frozen=True)
class Module:
    key: str
    name: str
    short: str
    part: str
    photo: str | None
    color: str
    optional: bool
    summary: str
    signals: tuple
    defaults: dict
    settings: dict = field(default_factory=dict)
    power: str = ""
    notes: str = ""

    def signal(self, key):
        return next(s for s in self.signals if s.key == key)


@dataclass(frozen=True)
class Rule:
    gpios: frozenset
    level: str          # "error" | "warning"
    text: str
    variant: str | None = None
    except_modules: frozenset = frozenset()


@dataclass(frozen=True)
class Board:
    id: str
    name: str
    chip: str
    flash_mb: int
    psram: str
    photo: str
    left: tuple
    right: tuple
    labels: dict
    rules: tuple

    @property
    def header_gpios(self):
        """Các GPIO có chân cắm trên devkit, theo thứ tự tăng dần."""
        return sorted({int(p) for p in self.left + self.right if p.isdigit()})

    def label(self, gpio):
        name = self.labels.get(str(gpio))
        return f"GPIO{gpio} ({name})" if name else f"GPIO{gpio}"

    def rules_for(self, gpio, variant, module_key=None):
        out = []
        for rule in self.rules:
            if gpio not in rule.gpios:
                continue
            if rule.variant and rule.variant != variant:
                continue
            if module_key and module_key in rule.except_modules:
                continue
            out.append(rule)
        return out


def _load(name):
    with open(paths.data_file(name), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def board():
    raw = _load("board-esp32s3-n16r8.json")
    rules = tuple(Rule(gpios=frozenset(r["gpios"]), level=r["level"], text=r["text"], variant=r.get("variant"),
                       except_modules=frozenset(r.get("except", []))) for r in raw["rules"])
    return Board(id=raw["id"], name=raw["name"], chip=raw["chip"], flash_mb=raw["flash_mb"], psram=raw["psram"],
                 photo=raw["photo"], left=tuple(raw["header"]["left"]), right=tuple(raw["header"]["right"]),
                 labels=raw.get("labels", {}), rules=rules)


@lru_cache(maxsize=1)
def modules():
    out = []
    for m in _load("modules.json"):
        signals = tuple(Signal(s["key"], s["label"], s.get("optional", False)) for s in m["signals"])
        out.append(Module(key=m["key"], name=m["name"], short=m.get("short", m["name"]), part=m["part"],
                          photo=m.get("photo"), color=m["color"], optional=m["optional"], summary=m["summary"], signals=signals, defaults=m["defaults"],
                          settings=m.get("settings", {}), power=m.get("power", ""), notes=m.get("notes", "")))
    return tuple(out)


def module(key):
    return next(m for m in modules() if m.key == key)
