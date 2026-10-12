"""Lưu cài đặt, lịch sử tra cứu và tích hợp với Windows (tự chạy, shortcut).

Mọi thứ nằm trong %APPDATA%\\Dich và registry nhánh HKCU, nên không cần
quyền quản trị (phù hợp máy ở trường).
"""

import json
import os
import subprocess
import sys
import winreg
from pathlib import Path

APP_NAME = "Dịch"
APP_ID = "Dich"
DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_ID
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "history.json"
HISTORY_LIMIT = 50

FONT_MIN, FONT_MAX, FONT_DEFAULT = 12, 32, 17

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
HIDDEN_ARG = "--an"  # khởi động cùng Windows: chạy ngầm, không mở cửa sổ

DEFAULTS = {
    "font_size": FONT_DEFAULT,
    "first_run_done": False,
}


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # không lưu được thì thôi, không làm phiền người dùng


class Settings:
    def __init__(self):
        self._data = {**DEFAULTS, **_read_json(SETTINGS_FILE, {})}

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value) -> None:
        self._data[key] = value
        _write_json(SETTINGS_FILE, self._data)

    @property
    def font_size(self) -> int:
        return max(FONT_MIN, min(FONT_MAX, int(self.get("font_size"))))


class History:
    """Các lượt tra gần nhất, mới nhất ở đầu danh sách."""

    def __init__(self):
        data = _read_json(HISTORY_FILE, [])
        self.items: list[dict] = data if isinstance(data, list) else []

    def add(self, source: str, translated: str) -> None:
        source, translated = source.strip(), translated.strip()
        if not source or not translated:
            return
        # Đang gõ dở ("subm" rồi "submit") thì chỉ giữ bản cuối cùng.
        if self.items:
            last = self.items[0].get("source", "")
            if source.startswith(last) or last.startswith(source):
                self.items.pop(0)
        self.items = [i for i in self.items if i.get("source") != source]
        self.items.insert(0, {"source": source, "translated": translated})
        del self.items[HISTORY_LIMIT:]
        _write_json(HISTORY_FILE, self.items)

    def clear(self) -> None:
        self.items = []
        _write_json(HISTORY_FILE, self.items)


# --- Tích hợp Windows -------------------------------------------------------

def is_frozen() -> bool:
    """Đang chạy từ file .exe đã đóng gói (không phải chạy bằng python)."""
    return getattr(sys, "frozen", False)


def _launch_command(*args: str) -> str:
    if is_frozen():
        parts = [sys.executable, *args]
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        parts = [str(pythonw if pythonw.exists() else sys.executable), "-m", "dich", *args]
    return subprocess.list2cmdline(parts)


def autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_ID)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, _launch_command(HIDDEN_ARG))
            else:
                winreg.DeleteValue(key, APP_ID)
    except OSError:
        pass


def create_shortcuts() -> bool:
    """Tạo shortcut ngoài Desktop và trong Start Menu (chỉ khi chạy bản .exe).

    Windows không cho chương trình tự ghim lên taskbar, nên việc ghim phải
    làm tay: chuột phải vào shortcut → "Pin to taskbar".
    """
    if not is_frozen():
        return False
    exe = sys.executable
    targets = [
        Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop",
        Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
    ]
    ok = False
    for folder in targets:
        if not folder.is_dir():
            continue
        lnk = folder / f"{APP_NAME}.lnk"
        script = (
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:DICH_LNK);"
            "$s.TargetPath=$env:DICH_EXE;"
            "$s.WorkingDirectory=(Split-Path $env:DICH_EXE);"
            "$s.IconLocation=$env:DICH_EXE+',0';"
            "$s.Description='Dịch nhanh tiếng Anh sang tiếng Việt';"
            "$s.Save()"
        )
        env = {**os.environ, "DICH_LNK": str(lnk), "DICH_EXE": exe}
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                env=env, timeout=15, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            ok = True
        except (OSError, subprocess.SubprocessError):
            pass
    return ok
