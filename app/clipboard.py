import tkinter as tk
import ctypes
import platform
import time

from app.binder import parse_hotkey
from app.constants import HOTKEY_CLIPBOARD_RESTORE_SECONDS, HOTKEY_PASTE_SETTLE_SECONDS

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008


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


def send_hotkey_to_active_window(hotkey: str) -> bool:
    """
    Отправляет клавишу/комбинацию в активное окно (Windows).
    Примеры: "T", "F6", "Ctrl+Y".
    """
    if platform.system() != "Windows":
        return False

    try:
        modifiers, key_vk, _normalized = parse_hotkey(hotkey)
    except Exception:
        return False

    return _send_key_combo_windows(modifiers, key_vk)


def release_pressed_modifiers_windows() -> None:
    if platform.system() != "Windows":
        return

    try:
        user32 = ctypes.windll.user32
    except Exception:
        return

    modifier_vks = [0xA2, 0xA3, 0xA4, 0xA5, 0xA0, 0xA1, 0x5B, 0x5C]
    for vk in modifier_vks:
        try:
            if user32.GetAsyncKeyState(vk) & 0x8000:
                _send_key_event_windows(vk, is_keyup=True)
        except Exception:
            continue


def _snapshot_clipboard_text(window: tk.Misc) -> tuple[str, bool]:
    try:
        value = window.clipboard_get()
    except tk.TclError:
        return "", False

    if not isinstance(value, str):
        return "", False
    return value, True


def _send_ctrl_v_windows() -> bool:
    return _send_key_combo_windows(MOD_CONTROL, 0x56)


def _send_enter_windows() -> bool:
    return _send_key_combo_windows(0, 0x0D)


def _send_key_combo_windows(modifiers: int, key_vk: int) -> bool:
    vk_control = 0x11
    vk_alt = 0x12
    vk_shift = 0x10
    vk_win_left = 0x5B

    pressed_mods: list[int] = []
    try:
        if modifiers & MOD_CONTROL:
            _send_key_event_windows(vk_control, is_keyup=False)
            pressed_mods.append(vk_control)
        if modifiers & MOD_ALT:
            _send_key_event_windows(vk_alt, is_keyup=False)
            pressed_mods.append(vk_alt)
        if modifiers & MOD_SHIFT:
            _send_key_event_windows(vk_shift, is_keyup=False)
            pressed_mods.append(vk_shift)
        if modifiers & MOD_WIN:
            _send_key_event_windows(vk_win_left, is_keyup=False)
            pressed_mods.append(vk_win_left)

        if not _send_key_event_windows(key_vk, is_keyup=False):
            return False
        if not _send_key_event_windows(key_vk, is_keyup=True):
            return False

        for vk in reversed(pressed_mods):
            _send_key_event_windows(vk, is_keyup=True)
        return True
    except Exception:
        for vk in reversed(pressed_mods):
            try:
                _send_key_event_windows(vk, is_keyup=True)
            except Exception:
                pass
        return False


def _send_key_event_windows(vk: int, is_keyup: bool) -> bool:
    if platform.system() != "Windows":
        return False

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_uint),
            ("time", ctypes.c_uint),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_uint), ("union", _INPUTUNION)]

    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0

    try:
        user32 = ctypes.windll.user32
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    except Exception:
        return False

    flags = 0
    is_extended = vk in {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}
    if scan:
        flags |= KEYEVENTF_SCANCODE
    if is_extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if is_keyup:
        flags |= KEYEVENTF_KEYUP

    key_input = KEYBDINPUT(
        wVk=0 if scan else vk,
        wScan=scan if scan else 0,
        dwFlags=flags,
        time=0,
        dwExtraInfo=None,
    )
    event = INPUT(type=INPUT_KEYBOARD, union=_INPUTUNION(ki=key_input))

    try:
        sent = user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
        return sent == 1
    except Exception:
        return False
