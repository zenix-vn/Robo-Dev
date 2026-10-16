"""Điểm vào của Robo Dev (tương đương python -m robodev); PyInstaller cũng đóng gói từ file này.

Chạy bằng Python chung của máy (py run.py) thì tự chuyển sang môi trường ảo .venv bên cạnh.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(HERE, ".venv", "Scripts", "python.exe")


def _relaunch_in_venv():
    if getattr(sys, "frozen", False):
        return
    try:
        import PySide6  # noqa: F401
        return
    except ImportError:
        pass
    if os.path.isfile(VENV_PYTHON) and os.path.abspath(sys.executable).lower() != VENV_PYTHON.lower():
        sys.exit(subprocess.call([VENV_PYTHON, os.path.abspath(__file__), *sys.argv[1:]]))
    sys.exit("Thiếu thư viện. Cài bằng:\n"
             f"  py -m venv \"{os.path.join(HERE, '.venv')}\"\n"
             f"  \"{VENV_PYTHON}\" -m pip install -r \"{os.path.join(HERE, 'requirements.txt')}\"")


_relaunch_in_venv()

from robodev.__main__ import main  # noqa: E402

sys.exit(main())
