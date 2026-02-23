import os
import sys
import re

from app.constants import APP_VERSION_ENV, UPDATE_CHECK_TIMEOUT_SECONDS, UPDATE_INFO_URL_ENV

# Релизные значения. Используются в собранном .exe (frozen).
RELEASE_APP_VERSION = "0.1.0"
RELEASE_UPDATE_INFO_URL = "https://raw.githubusercontent.com/Alaaois/rp-binder/refs/heads/main/version.json"


def _resolve_app_version() -> str:
    if getattr(sys, "frozen", False):
        return RELEASE_APP_VERSION

    # Dev-режим: можно переопределять через .env / env.
    return os.getenv(APP_VERSION_ENV, RELEASE_APP_VERSION).strip() or RELEASE_APP_VERSION


def _resolve_update_info_url() -> str:
    if getattr(sys, "frozen", False):
        return RELEASE_UPDATE_INFO_URL

    # Dev-режим: можно переопределять через .env / env.
    return os.getenv(UPDATE_INFO_URL_ENV, RELEASE_UPDATE_INFO_URL).strip() or RELEASE_UPDATE_INFO_URL


APP_VERSION = _resolve_app_version()
UPDATE_INFO_URL = _resolve_update_info_url()


def check_for_updates(timeout: int = UPDATE_CHECK_TIMEOUT_SECONDS) -> dict | None:
    """
    Возвращает словарь с данными обновления, если есть новая версия.
    Иначе None.
    """
    try:
        import requests

        response = requests.get(UPDATE_INFO_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return None

        remote_version = str(payload.get("version", "")).strip()
        if _is_newer(remote_version, APP_VERSION):
            return payload
        return None
    except Exception:
        # Не ломаем приложение из-за недоступного интернета/гитхаба
        return None


def _is_newer(remote: str, local: str) -> bool:
    def parse(v: str) -> tuple[int, ...]:
        # Поддержка "1.2.3", "v1.2.3", "1.2"
        numbers = re.findall(r"\d+", v or "")
        if not numbers:
            return tuple()
        return tuple(int(value) for value in numbers)

    try:
        return parse(remote) > parse(local)
    except Exception:
        return False
