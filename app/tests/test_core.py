import queue
import threading
import time

import pytest

from robodev.core import firmware, jobs, link, pins, profile, simulator


def collect():
    events = []
    return events, lambda *e: events.append(e)


def done_of(events):
    return next(e for e in events if e[0] == "done")


@pytest.fixture(autouse=True)
def fresh_demo():
    simulator.DEVICE.__init__()
    yield


# Chân -----------------------------------------------------------------------------------
def test_default_pins_have_no_errors():
    issues = pins.validate(profile.default_hw())
    assert not [i for i in issues if i.level == "error"]
    # GPIO3 (strapping) và GPIO43/44 (TX/RX ở biến thể usb) chỉ là cảnh báo
    assert {i.gpio for i in issues} == {3, 43, 44}


def test_duplicate_pin_is_error():
    hw = profile.default_hw()
    hw["motors"]["in1"] = hw["mic"]["ws"]
    errors = [i for i in pins.validate(hw) if i.level == "error"]
    assert errors and all(i.gpio == 4 for i in errors)


def test_psram_and_variant_rules():
    hw = profile.default_hw()
    hw["sensor"]["sda"] = 35
    assert any(i.gpio == 35 and i.level == "error" for i in pins.validate(hw))
    hw = profile.default_hw()
    hw["variant"] = "uart"
    assert any(i.gpio == 43 and i.level == "error" for i in pins.validate(hw))


def test_disabled_module_is_ignored():
    hw = profile.default_hw()
    hw["lcd"]["enabled"] = False
    assert not [i for i in pins.validate(hw) if i.gpio in (43, 44)]


def test_boot_pin_only_for_button():
    hw = profile.default_hw()
    hw["led"]["pin"] = 0
    assert any(i.module == "led" and i.gpio == 0 and i.level == "error" for i in pins.validate(hw))


# Hồ sơ ----------------------------------------------------------------------------------
def test_default_cfg_payload_is_minimal():
    project = profile.new_project()
    assert profile.cfg_payload(project, {"cfg", "wifi", "test", "hw", "commands"}) == {"version": 1}
    assert profile.cfg_payload(project, {"cfg", "wifi", "test"}) == {"version": 1}


def test_changes_are_sent_and_expected():
    project = profile.new_project()
    project["cfg"]["motors"]["default_speed"] = 80
    project["hw"]["motors"]["invert_left"] = True
    # Firmware chưa có khối hw: đảo bánh gửi trong cfg.motors
    basic = profile.cfg_payload(project, {"cfg", "wifi", "test"})
    assert basic["motors"] == {"default_speed": 80, "invert_left": True}
    assert profile.expected_cfg(project, {"cfg", "wifi", "test"})["motors"]["invert_left"] is True
    assert "invert_left" not in profile.cfg_payload(project, {"cfg", "wifi", "test", "hw", "commands"}).get("motors", {})


def test_commands_sent_only_when_supported():
    project = profile.new_project()
    project["commands"] = profile.sample_commands()
    assert "commands" in profile.cfg_payload(project, {"cfg", "wifi", "test", "hw", "commands"})
    assert "commands" not in profile.cfg_payload(project, {"cfg", "wifi", "test"})


def test_roundtrip(tmp_path):
    project = profile.new_project("Bim")
    project["commands"] = profile.sample_commands()
    path = tmp_path / ("a" + profile.EXTENSION)
    profile.save(project, str(path))
    loaded = profile.load(str(path))
    assert loaded == project


def test_command_validation():
    assert profile.validate_commands(profile.sample_commands()) == []
    bad = {"Chào": {"description": "", "steps": [{"wait": 40000}]}}
    errors = profile.validate_commands(bad)
    assert len(errors) == 3


def test_firmware_discovery():
    packages = firmware.discover()
    assert packages and all(p.name.startswith("Robo Dev") for p in packages)


# Luồng với mạch mô phỏng ----------------------------------------------------------------
def test_demo_check():
    events, emit = collect()
    jobs.job_check(link.DEMO_PORT, emit, threading.Event())
    result = next(e[1] for e in events if e[0] == "check")
    assert result["chip"][0] and result["firmware"][0]
    assert "hw" in result["info"]["caps"]
    assert result["info"]["sensor"] == "vl6180x"


def test_demo_apply_changes_pins_and_cfg():
    project = profile.new_project()
    project["hw"]["motors"]["in1"] = 9
    project["cfg"]["motors"]["default_speed"] = 85
    events, emit = collect()
    jobs.job_apply(link.DEMO_PORT, project, emit, threading.Event())
    assert done_of(events)[1], events
    assert simulator.DEVICE.hw["motors"]["in1"] == 9
    assert simulator.DEVICE.cfg["motors"]["default_speed"] == 85


def test_demo_flash_full_with_wifi_gets_code():
    project = profile.new_project()
    events, emit = collect()
    pkg = firmware.discover()[0]
    t0 = time.time()
    jobs.job_flash(link.DEMO_PORT, pkg, "full", False, project, "NhaMinh", "12345678", emit, threading.Event())
    ok, message = done_of(events)[1:]
    assert ok, message
    assert ("code", "482916") in events
    assert time.time() - t0 < 30


def test_demo_wrong_password_fails():
    events, emit = collect()
    jobs.job_wifi(link.DEMO_PORT, "NhaMinh", "sai", emit, threading.Event())
    assert not done_of(events)[1]
    assert ("step", "wifi", "fail") == next(e for e in events if e[0] == "step" and e[1] == "wifi" and e[2] == "fail")[:3]


def test_demo_monitor_runs_tests():
    events, emit = collect()
    commands, stop = queue.Queue(), threading.Event()
    worker = threading.Thread(target=jobs.job_monitor, args=(link.DEMO_PORT, commands, emit, stop))
    worker.start()
    for module, step in (("speaker", "tone"), ("mic", "level"), ("sensor", "read")):
        commands.put(("test", module, step))
    deadline = time.time() + 10
    while time.time() < deadline and sum(e[0] == "test" for e in events) < 3:
        time.sleep(0.1)
    stop.set()
    worker.join(5)
    results = {e[1]: e for e in events if e[0] == "test"}
    assert set(results) == {"speaker", "mic", "sensor"}
    assert all(r[3] for r in results.values())
    assert "mm=" in results["sensor"][4] and "avg_abs=" in results["mic"][4]
