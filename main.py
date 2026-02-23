import platform
import ctypes
import sys
from pathlib import Path
import customtkinter as ctk
from dotenv import load_dotenv

from app.constants import APP_NAME


def _configure_windows_dpi() -> None:
    """Включает DPI awareness, чтобы UI не был размытым/кривым на Windows scaling."""
    if platform.system() != "Windows":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _load_environment() -> None:
    """Подгружает .env только в dev-режиме."""
    if getattr(sys, "frozen", False):
        return

    candidates: list[Path] = []

    # Для dev-запуска: корень проекта (рядом с main.py).
    candidates.append(Path(__file__).resolve().parent / ".env")

    # Также поддерживаем запуск из другой рабочей директории.
    candidates.append(Path.cwd() / ".env")

    seen: set[Path] = set()
    for env_path in candidates:
        if env_path in seen:
            continue
        seen.add(env_path)
        load_dotenv(env_path, override=False)


def main():
    if platform.system() != "Windows":
        raise SystemExit("RP Binder поддерживается только на Windows.")

    _load_environment()
    _configure_windows_dpi()
    _configure_ctk()

    from app.ui import RPAssistantApp

    app = RPAssistantApp()
    app.mainloop()


def _configure_ctk() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)


def _set_process_title() -> None:
    if platform.system() != "Windows":
        return

    try:
        ctypes.windll.kernel32.SetConsoleTitleW(APP_NAME)
    except Exception:
        pass

if __name__ == "__main__":
    _set_process_title()
    main()
