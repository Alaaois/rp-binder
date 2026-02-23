import tkinter as tk
import ctypes
import platform
import time

from app.constants import HOTKEY_CLIPBOARD_RESTORE_SECONDS, HOTKEY_PASTE_SETTLE_SECONDS


def copy_to_clipboard(window: tk.Misc, text: str) -> None:
    """Копирует текст в системный буфер обмена."""
    window.clipboard_clear()
    window.clipboard_append(text)
    window.update_idletasks()


def paste_text_to_active_window(
    window: tk.Misc,
    text: str,
    press_enter: bool = False,
    enter_delay_seconds: float = 0.0,
    restore_clipboard: bool = False,
) -> bool:
    """
    Безопасная вставка:
    1) временно кладет текст в буфер
    2) отправляет Ctrl+V
    3) восстанавливает предыдущий текстовый буфер (если удалось прочитать)

    Возвращает True, если авто-вставка выполнена.
    """
    if platform.system() != "Windows":
        return False

    previous_text, has_text_snapshot = ("", False)
    if restore_clipboard:
        previous_text, has_text_snapshot = _snapshot_clipboard_text(window)
    copy_to_clipboard(window, text)
    time.sleep(HOTKEY_PASTE_SETTLE_SECONDS)

    if not _send_ctrl_v_windows():
        if restore_clipboard and has_text_snapshot:
            copy_to_clipboard(window, previous_text)
        return False

    if press_enter:
        if enter_delay_seconds > 0:
            time.sleep(enter_delay_seconds)
        if not _send_enter_windows():
            if restore_clipboard and has_text_snapshot:
                copy_to_clipboard(window, previous_text)
            return False

    if restore_clipboard and has_text_snapshot:
        time.sleep(HOTKEY_CLIPBOARD_RESTORE_SECONDS)
        copy_to_clipboard(window, previous_text)

    return True


def _snapshot_clipboard_text(window: tk.Misc) -> tuple[str, bool]:
    try:
        value = window.clipboard_get()
    except tk.TclError:
        return "", False

    if not isinstance(value, str):
        return "", False
    return value, True


def _send_ctrl_v_windows() -> bool:
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return False

    keyeventf_keyup = 0x0002
    vk_control = 0x11
    vk_v = 0x56

    try:
        user32.keybd_event(vk_control, 0, 0, 0)
        user32.keybd_event(vk_v, 0, 0, 0)
        user32.keybd_event(vk_v, 0, keyeventf_keyup, 0)
        user32.keybd_event(vk_control, 0, keyeventf_keyup, 0)
        return True
    except Exception:
        return False


def _send_enter_windows() -> bool:
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return False

    keyeventf_keyup = 0x0002
    vk_enter = 0x0D

    try:
        user32.keybd_event(vk_enter, 0, 0, 0)
        user32.keybd_event(vk_enter, 0, keyeventf_keyup, 0)
        return True
    except Exception:
        return False
