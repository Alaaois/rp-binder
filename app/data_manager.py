import json
import os
import sys
import copy
import uuid
from pathlib import Path
from typing import Dict, Any

from app.constants import (
    APP_NAME,
    CHAT_OPEN_DELAY_DEFAULT_MS,
    CHAT_OPEN_DELAY_MAX_MS,
    CHAT_OPEN_DELAY_MIN_MS,
    CHAT_OPEN_HOTKEY_DEFAULT,
    PANIC_HOTKEY_DEFAULT,
    PASTE_ENTER_DEFAULT_DELAY_MS,
    PASTE_ENTER_MAX_DELAY_MS,
    PASTE_ENTER_MIN_DELAY_MS,
)
from app.models import ProfilesPayload, UserSettings


def _get_runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return Path(__file__).resolve().parent.parent


def _get_user_data_dir() -> Path:
    roaming = os.getenv("APPDATA")
    if roaming:
        return Path(roaming) / APP_NAME
    return Path.home() / "AppData" / "Roaming" / APP_NAME


BASE_DIR = _get_runtime_base_dir()
DATA_DIR = BASE_DIR / "data"
DEFAULT_PROFILE_PATH = DATA_DIR / "default_profile.json"
USER_DATA_DIR = _get_user_data_dir()
SETTINGS_PATH = USER_DATA_DIR / "settings.json"
USER_PROFILES_PATH = USER_DATA_DIR / "profiles.json"


ALLOWED_SEND_MODES = {"copy", "paste", "paste_enter", "chat_send"}


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("Некорректный JSON: элемент категории должен быть объектом")

    if "title" not in item or "text" not in item:
        raise ValueError("Некорректный JSON: у элемента нужны поля title и text")

    title = item.get("title")
    text = item.get("text")
    if not isinstance(title, str) or not isinstance(text, str):
        raise ValueError("Некорректный JSON: поля title и text должны быть строками")

    normalized = dict(item)
    item_id = normalized.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        normalized["item_id"] = uuid.uuid4().hex
    else:
        normalized["item_id"] = item_id.strip()

    hotkey = normalized.get("hotkey", "")
    normalized["hotkey"] = hotkey.strip() if isinstance(hotkey, str) else ""

    send_mode = normalized.get("send_mode", "copy")
    if not isinstance(send_mode, str):
        send_mode = "copy"
    send_mode = send_mode.strip().lower()
    if send_mode not in ALLOWED_SEND_MODES:
        send_mode = "copy"
    normalized["send_mode"] = send_mode

    delay_raw = normalized.get("delay_ms", PASTE_ENTER_DEFAULT_DELAY_MS)
    try:
        delay_value = int(delay_raw)
    except Exception:
        delay_value = PASTE_ENTER_DEFAULT_DELAY_MS
    delay_value = max(PASTE_ENTER_MIN_DELAY_MS, min(PASTE_ENTER_MAX_DELAY_MS, delay_value))
    normalized["delay_ms"] = delay_value

    chat_open_hotkey = normalized.get("chat_open_hotkey", CHAT_OPEN_HOTKEY_DEFAULT)
    if isinstance(chat_open_hotkey, str) and chat_open_hotkey.strip():
        normalized["chat_open_hotkey"] = chat_open_hotkey.strip()
    else:
        normalized["chat_open_hotkey"] = CHAT_OPEN_HOTKEY_DEFAULT

    chat_open_delay_raw = normalized.get("chat_open_delay_ms", CHAT_OPEN_DELAY_DEFAULT_MS)
    try:
        chat_open_delay_value = int(chat_open_delay_raw)
    except Exception:
        chat_open_delay_value = CHAT_OPEN_DELAY_DEFAULT_MS
    chat_open_delay_value = max(CHAT_OPEN_DELAY_MIN_MS, min(CHAT_OPEN_DELAY_MAX_MS, chat_open_delay_value))
    normalized["chat_open_delay_ms"] = chat_open_delay_value

    enabled_raw = normalized.get("enabled", False)
    if isinstance(enabled_raw, bool):
        enabled = enabled_raw
    elif isinstance(enabled_raw, (int, float)):
        enabled = bool(enabled_raw)
    elif isinstance(enabled_raw, str):
        enabled = enabled_raw.strip().lower() in {"1", "true", "yes", "on", "да"}
    else:
        enabled = False
    normalized["enabled"] = enabled

    chat_send_each_line_raw = normalized.get("chat_send_each_line", False)
    if isinstance(chat_send_each_line_raw, bool):
        chat_send_each_line = chat_send_each_line_raw
    elif isinstance(chat_send_each_line_raw, (int, float)):
        chat_send_each_line = bool(chat_send_each_line_raw)
    elif isinstance(chat_send_each_line_raw, str):
        chat_send_each_line = chat_send_each_line_raw.strip().lower() in {"1", "true", "yes", "on", "да"}
    else:
        chat_send_each_line = False
    normalized["chat_send_each_line"] = chat_send_each_line

    return normalized


def _validate_profile(data: Dict[str, Any]) -> None:
    profile_name = data.get("profile_name")
    if not isinstance(profile_name, str) or not profile_name.strip():
        raise ValueError("Некорректный JSON: у профиля нужно поле profile_name")

    if "categories" not in data or not isinstance(data["categories"], list):
        raise ValueError("Некорректный JSON: отсутствует список categories")

    for category in data["categories"]:
        if "name" not in category or "items" not in category:
            raise ValueError("Некорректный JSON: у категории нужны поля name и items")
        if not isinstance(category["items"], list):
            raise ValueError("Некорректный JSON: items должен быть списком")
        for item in category["items"]:
            _normalize_item(item)


def _normalize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        raise ValueError("Некорректный JSON: каждый профиль в profiles должен быть объектом")

    item = dict(profile)
    _validate_profile(item)

    normalized_categories: list[Dict[str, Any]] = []
    for category in item.get("categories", []):
        normalized_category = dict(category)
        normalized_items: list[Dict[str, Any]] = []
        for raw_item in normalized_category.get("items", []):
            normalized_items.append(_normalize_item(raw_item))
        normalized_category["items"] = normalized_items
        normalized_categories.append(normalized_category)

    item["categories"] = normalized_categories
    return item


def _normalize_profiles_payload(payload: Dict[str, Any]) -> ProfilesPayload:
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("Некорректный JSON: ожидается непустой список profiles")

    normalized_profiles: list[Dict[str, Any]] = []
    for profile in profiles:
        normalized_profiles.append(_normalize_profile(profile))

    return {
        "profiles": normalized_profiles,
        "version": str(payload.get("version", "1.0")),
    }


def _read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _normalize_settings(payload: Dict[str, Any]) -> UserSettings:
    nick = payload.get("nick", "")
    position = payload.get("position", "")
    panic_hotkey = payload.get("panic_hotkey", PANIC_HOTKEY_DEFAULT)
    normalized_panic_hotkey = (
        panic_hotkey.strip() if isinstance(panic_hotkey, str) and panic_hotkey.strip() else PANIC_HOTKEY_DEFAULT
    )

    return {
        "nick": nick.strip() if isinstance(nick, str) else "",
        "position": position.strip() if isinstance(position, str) else "",
        "binder_enabled": bool(payload.get("binder_enabled", False)),
        "panic_hotkey": normalized_panic_hotkey,
    }


class DataManager:
    def __init__(self):
        self.current_data: ProfilesPayload | None = None

    def load_profile(self, path: str | Path) -> ProfilesPayload:
        path = Path(path)
        payload = _read_json_file(path)

        if not isinstance(payload, dict):
            raise ValueError("Некорректный JSON: корень файла должен быть объектом")

        data = _normalize_profiles_payload(payload)
        self.current_data = data
        return data

    def load_default_profile(self) -> ProfilesPayload:
        return self.load_profile(DEFAULT_PROFILE_PATH)

    def load_active_profiles(self) -> ProfilesPayload:
        if USER_PROFILES_PATH.exists():
            return self.load_profile(USER_PROFILES_PATH)
        return self.load_default_profile()

    def import_profile(self, path: str | Path) -> ProfilesPayload:
        # Пока просто загрузка и замена текущего профиля
        return self.load_profile(path)

    @staticmethod
    def generate_item_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _norm_key(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lower()

    def merge_profiles(self, current_data: Dict[str, Any], incoming_data: Dict[str, Any]) -> tuple[ProfilesPayload, Dict[str, int]]:
        """
        Объединяет incoming_data в current_data без дублей фраз.
        Возвращает (merged_data, stats).
        """
        current = _normalize_profiles_payload(current_data)
        incoming = _normalize_profiles_payload(incoming_data)

        merged = copy.deepcopy(current)
        stats = {
            "profiles_added": 0,
            "categories_added": 0,
            "items_added": 0,
            "items_skipped": 0,
        }

        merged_profiles = merged.get("profiles", [])
        incoming_profiles = incoming.get("profiles", [])

        for incoming_profile in incoming_profiles:
            incoming_profile_name = self._norm_key(incoming_profile.get("profile_name"))
            target_profile = None

            for profile in merged_profiles:
                if self._norm_key(profile.get("profile_name")) == incoming_profile_name:
                    target_profile = profile
                    break

            if target_profile is None:
                merged_profiles.append(copy.deepcopy(incoming_profile))
                stats["profiles_added"] += 1
                incoming_categories = incoming_profile.get("categories", [])
                if isinstance(incoming_categories, list):
                    stats["categories_added"] += len(incoming_categories)
                    for category in incoming_categories:
                        items = category.get("items", []) if isinstance(category, dict) else []
                        if isinstance(items, list):
                            stats["items_added"] += len(items)
                continue

            target_categories = target_profile.get("categories", [])
            incoming_categories = incoming_profile.get("categories", [])

            for incoming_category in incoming_categories:
                incoming_category_name = self._norm_key(incoming_category.get("name"))
                target_category = None

                for category in target_categories:
                    if self._norm_key(category.get("name")) == incoming_category_name:
                        target_category = category
                        break

                if target_category is None:
                    target_categories.append(copy.deepcopy(incoming_category))
                    stats["categories_added"] += 1
                    incoming_items = incoming_category.get("items", [])
                    if isinstance(incoming_items, list):
                        stats["items_added"] += len(incoming_items)
                    continue

                target_items = target_category.get("items", [])
                incoming_items = incoming_category.get("items", [])
                existing_keys = {
                    (self._norm_key(item.get("title")), self._norm_key(item.get("text")))
                    for item in target_items
                    if isinstance(item, dict)
                }

                for incoming_item in incoming_items:
                    key = (
                        self._norm_key(incoming_item.get("title")),
                        self._norm_key(incoming_item.get("text")),
                    )
                    if key in existing_keys:
                        stats["items_skipped"] += 1
                        continue

                    target_items.append(copy.deepcopy(incoming_item))
                    existing_keys.add(key)
                    stats["items_added"] += 1

        normalized_merged = _normalize_profiles_payload(merged)
        self.current_data = normalized_merged
        return normalized_merged, stats

    def save_active_profiles(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("Некорректные данные профилей для сохранения")

        normalized = _normalize_profiles_payload(data)
        _write_json_file(USER_PROFILES_PATH, normalized)

        self.current_data = normalized

    def load_settings(self) -> UserSettings:
        default: UserSettings = {
            "nick": "",
            "position": "",
            "binder_enabled": False,
            "panic_hotkey": PANIC_HOTKEY_DEFAULT,
        }

        if not SETTINGS_PATH.exists():
            return default

        try:
            raw = SETTINGS_PATH.read_text(encoding="utf-8").strip()
            if not raw:
                return default

            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return default
        except Exception:
            return default

        return _normalize_settings(payload)

    def save_settings(self, settings: Dict[str, Any]) -> None:
        payload: UserSettings = {
            "nick": str(settings.get("nick", "")).strip(),
            "position": str(settings.get("position", "")).strip(),
            "binder_enabled": bool(settings.get("binder_enabled", False)),
            "panic_hotkey": str(settings.get("panic_hotkey", PANIC_HOTKEY_DEFAULT)).strip() or PANIC_HOTKEY_DEFAULT,
        }

        _write_json_file(SETTINGS_PATH, payload)
