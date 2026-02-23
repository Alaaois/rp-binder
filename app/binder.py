import ctypes
import platform
import re
import threading
import time
from ctypes import wintypes
from typing import Callable


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

_MODIFIER_ALIASES = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "meta": MOD_WIN,
    "super": MOD_WIN,
}

_DISPLAY_MODIFIERS = [
    (MOD_CONTROL, "Ctrl"),
    (MOD_ALT, "Alt"),
    (MOD_SHIFT, "Shift"),
    (MOD_WIN, "Win"),
]

_KEY_ALIASES = {
    "space": (0x20, "Space"),
    "tab": (0x09, "Tab"),
    "enter": (0x0D, "Enter"),
    "return": (0x0D, "Enter"),
    "esc": (0x1B, "Esc"),
    "escape": (0x1B, "Esc"),
    "backspace": (0x08, "Backspace"),
    "delete": (0x2E, "Delete"),
    "del": (0x2E, "Delete"),
    "insert": (0x2D, "Insert"),
    "ins": (0x2D, "Insert"),
    "home": (0x24, "Home"),
    "end": (0x23, "End"),
    "pageup": (0x21, "PgUp"),
    "pgup": (0x21, "PgUp"),
    "pagedown": (0x22, "PgDn"),
    "pgdn": (0x22, "PgDn"),
    "up": (0x26, "Up"),
    "down": (0x28, "Down"),
    "left": (0x25, "Left"),
    "right": (0x27, "Right"),
    "num0": (0x60, "Num0"),
    "numpad0": (0x60, "Num0"),
    "kp_0": (0x60, "Num0"),
    "num1": (0x61, "Num1"),
    "numpad1": (0x61, "Num1"),
    "kp_1": (0x61, "Num1"),
    "num2": (0x62, "Num2"),
    "numpad2": (0x62, "Num2"),
    "kp_2": (0x62, "Num2"),
    "num3": (0x63, "Num3"),
    "numpad3": (0x63, "Num3"),
    "kp_3": (0x63, "Num3"),
    "num4": (0x64, "Num4"),
    "numpad4": (0x64, "Num4"),
    "kp_4": (0x64, "Num4"),
    "num5": (0x65, "Num5"),
    "numpad5": (0x65, "Num5"),
    "kp_5": (0x65, "Num5"),
    "num6": (0x66, "Num6"),
    "numpad6": (0x66, "Num6"),
    "kp_6": (0x66, "Num6"),
    "num7": (0x67, "Num7"),
    "numpad7": (0x67, "Num7"),
    "kp_7": (0x67, "Num7"),
    "num8": (0x68, "Num8"),
    "numpad8": (0x68, "Num8"),
    "kp_8": (0x68, "Num8"),
    "num9": (0x69, "Num9"),
    "numpad9": (0x69, "Num9"),
    "kp_9": (0x69, "Num9"),
    "numadd": (0x6B, "NumPlus"),
    "numpadadd": (0x6B, "NumPlus"),
    "numplus": (0x6B, "NumPlus"),
    "numpadplus": (0x6B, "NumPlus"),
    "num+": (0x6B, "NumPlus"),
    "kp_add": (0x6B, "NumPlus"),
    "num-": (0x6D, "NumMinus"),
    "numsub": (0x6D, "NumMinus"),
    "numpadsub": (0x6D, "NumMinus"),
    "numminus": (0x6D, "NumMinus"),
    "numpadminus": (0x6D, "NumMinus"),
    "kp_subtract": (0x6D, "NumMinus"),
    "num*": (0x6A, "NumMultiply"),
    "nummul": (0x6A, "NumMultiply"),
    "numpadmul": (0x6A, "NumMultiply"),
    "nummultiply": (0x6A, "NumMultiply"),
    "numpadmultiply": (0x6A, "NumMultiply"),
    "kp_multiply": (0x6A, "NumMultiply"),
    "num/": (0x6F, "NumDivide"),
    "numdiv": (0x6F, "NumDivide"),
    "numpaddiv": (0x6F, "NumDivide"),
    "numdivide": (0x6F, "NumDivide"),
    "numpaddivide": (0x6F, "NumDivide"),
    "kp_divide": (0x6F, "NumDivide"),
    "numdecimal": (0x6E, "NumDecimal"),
    "numpaddecimal": (0x6E, "NumDecimal"),
    "kp_decimal": (0x6E, "NumDecimal"),
    "numenter": (0x0D, "NumEnter"),
    "kp_enter": (0x0D, "NumEnter"),
}


def parse_hotkey(hotkey: str) -> tuple[int, int, str]:
    if not isinstance(hotkey, str):
        raise ValueError("Горячая клавиша должна быть строкой.")

    parts = [part.strip() for part in hotkey.split("+") if part.strip()]
    if not parts:
        raise ValueError("Введите горячую клавишу (например End, Ctrl+1 или Alt+F2).")

    modifiers = 0
    key_vk: int | None = None
    key_display: str | None = None

    for part in parts:
        token = part.lower()
        mod_value = _MODIFIER_ALIASES.get(token)
        if mod_value is not None:
            modifiers |= mod_value
            continue

        if key_vk is not None:
            raise ValueError("Можно указать только одну основную клавишу.")
        key_vk, key_display = _parse_key_token(token)

    if key_vk is None or key_display is None:
        raise ValueError("Не указана основная клавиша.")

    display_parts = [name for mask, name in _DISPLAY_MODIFIERS if modifiers & mask]
    display_parts.append(key_display)
    normalized = "+".join(display_parts)
    return modifiers, key_vk, normalized


def normalize_hotkey(hotkey: str) -> str:
    _, _, normalized = parse_hotkey(hotkey)
    return normalized


def _parse_key_token(token: str) -> tuple[int, str]:
    alias = _KEY_ALIASES.get(token)
    if alias is not None:
        return alias

    if re.fullmatch(r"[a-z]", token):
        char = token.upper()
        return ord(char), char

    if re.fullmatch(r"\d", token):
        return ord(token), token

    f_match = re.fullmatch(r"f([1-9]|1\d|2[0-4])", token)
    if f_match:
        number = int(f_match.group(1))
        return 0x70 + number - 1, f"F{number}"

    raise ValueError(f"Неизвестная клавиша: {token}")


class GlobalHotkeyBinder:
    def __init__(self, on_trigger: Callable[[str], None]):
        self._on_trigger = on_trigger
        self._supported = platform.system() == "Windows"
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._start_event = threading.Event()
        self._bindings: dict[str, tuple[int, int, str]] = {}
        self._start_errors: list[str] = []
        self._active_count = 0

    @property
    def is_supported(self) -> bool:
        return self._supported

    @property
    def active_count(self) -> int:
        return self._active_count

    def configure(self, bindings: dict[str, str]) -> tuple[int, list[str]]:
        parsed_bindings: dict[str, tuple[int, int, str]] = {}
        combo_to_item: dict[tuple[int, int], str] = {}
        issues: list[str] = []

        for item_id, hotkey in bindings.items():
            try:
                modifiers, vk, normalized = parse_hotkey(hotkey)
            except ValueError as err:
                issues.append(f"{item_id}: {err}")
                continue

            combo = (modifiers, vk)
            if combo in combo_to_item:
                issues.append(f"{item_id}: конфликт с {combo_to_item[combo]} ({normalized})")
                continue

            combo_to_item[combo] = item_id
            parsed_bindings[item_id] = (modifiers, vk, normalized)

        self.stop()

        if not parsed_bindings:
            return 0, issues

        if not self._supported:
            issues.append("Глобальные бинды поддерживаются только на Windows.")
            return 0, issues

        self._bindings = parsed_bindings
        self._start_errors = []
        self._active_count = 0
        self._stop_event.clear()
        self._start_event.clear()

        self._thread = threading.Thread(target=self._worker, daemon=True, name="global-hotkeys")
        self._thread.start()
        self._start_event.wait(timeout=1.5)

        issues.extend(self._start_errors)
        return self._active_count, issues

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._bindings = {}
        self._active_count = 0
        self._start_event.set()

    def _worker(self) -> None:
        user32 = ctypes.windll.user32
        id_to_item: dict[int, str] = {}
        registered_ids: list[int] = []
        next_id = 1

        for item_id, (modifiers, vk, normalized) in self._bindings.items():
            success = user32.RegisterHotKey(None, next_id, modifiers, vk)
            if success:
                id_to_item[next_id] = item_id
                registered_ids.append(next_id)
                next_id += 1
                continue

            self._start_errors.append(f"{item_id}: не удалось зарегистрировать {normalized}")

        self._active_count = len(registered_ids)
        self._start_event.set()

        msg = wintypes.MSG()
        while not self._stop_event.is_set():
            has_message = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE)
            if has_message:
                if msg.message == WM_HOTKEY:
                    hotkey_id = int(msg.wParam)
                    item_id = id_to_item.get(hotkey_id)
                    if item_id:
                        try:
                            self._on_trigger(item_id)
                        except Exception:
                            pass
            else:
                time.sleep(0.01)

        for hotkey_id in registered_ids:
            user32.UnregisterHotKey(None, hotkey_id)
