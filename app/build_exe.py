"""Đóng gói Robo Dev thành thư mục phát hành: Robo-Dev.exe + firmware/.

    py build_exe.py

Dùng môi trường ảo .venv bên cạnh (tự cài PyInstaller nếu thiếu). Kết quả ở ../releases/Robo-Dev/
(thư mục releases/ không commit).
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RELEASE = os.path.join(os.path.dirname(ROOT), "releases", "Robo-Dev")
WORK = os.path.join(ROOT, "build-pyinstaller")
VENV_PYTHON = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
PYTHON = VENV_PYTHON if os.path.isfile(VENV_PYTHON) else sys.executable


def has(module):
    return subprocess.run([PYTHON, "-c", f"import {module}"], capture_output=True).returncode == 0


if not has("PySide6"):
    print("Cài thư viện của ứng dụng vào", PYTHON)
    subprocess.run([PYTHON, "-m", "pip", "install", "-r", os.path.join(ROOT, "requirements.txt")], check=True)
if not has("PyInstaller"):
    print("Cài PyInstaller vào", PYTHON)
    subprocess.run([PYTHON, "-m", "pip", "install", "pyinstaller"], check=True)

cmd = [PYTHON, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--name", "Robo-Dev",
       "--distpath", os.path.join(WORK, "dist"), "--workpath", os.path.join(WORK, "work"), "--specpath", WORK,
       "--add-data", os.path.join(ROOT, "robodev", "data") + os.pathsep + os.path.join("robodev", "data"),
       "--collect-all", "esptool", "--collect-all", "esp_pylib", "--collect-all", "reedsolo",
       "--collect-all", "bitstring", "--collect-all", "tibs",
       "--hidden-import", "serial.tools.list_ports",
       "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtWebEngineWidgets",
       "--exclude-module", "PySide6.QtPdf", "--exclude-module", "tkinter",
       os.path.join(ROOT, "run.py")]
subprocess.run(cmd, check=True, cwd=ROOT)

os.makedirs(RELEASE, exist_ok=True)
shutil.copyfile(os.path.join(WORK, "dist", "Robo-Dev.exe"), os.path.join(RELEASE, "Robo-Dev.exe"))
source_fw = os.path.join(ROOT, "firmware")
if os.path.isdir(source_fw):
    shutil.copytree(source_fw, os.path.join(RELEASE, "firmware"), dirs_exist_ok=True)
print("Đã tạo", RELEASE)
