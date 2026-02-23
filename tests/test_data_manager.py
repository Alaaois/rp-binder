import json
import tempfile
import unittest
from pathlib import Path

import app.data_manager as dm


def _sample_payload(profile_name: str = "Тестовый профиль") -> dict:
    return {
        "version": "1.1",
        "profiles": [
            {
                "profile_name": profile_name,
                "categories": [
                    {
                        "name": "Отдел",
                        "items": [
                            {"title": "Команда", "text": "/me test"}
                        ],
                    }
                ],
            }
        ],
    }


class DataManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.default_profile_path = self.temp_path / "default_profile.json"
        self.user_profiles_path = self.temp_path / "profiles.json"
        self.settings_path = self.temp_path / "settings.json"

        self._original_default_profile_path = dm.DEFAULT_PROFILE_PATH
        self._original_user_profiles_path = dm.USER_PROFILES_PATH
        self._original_settings_path = dm.SETTINGS_PATH

        dm.DEFAULT_PROFILE_PATH = self.default_profile_path
        dm.USER_PROFILES_PATH = self.user_profiles_path
        dm.SETTINGS_PATH = self.settings_path

        self.default_profile_path.write_text(
            json.dumps(_sample_payload("Дефолт"), ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self):
        dm.DEFAULT_PROFILE_PATH = self._original_default_profile_path
        dm.USER_PROFILES_PATH = self._original_user_profiles_path
        dm.SETTINGS_PATH = self._original_settings_path
        self.temp_dir.cleanup()

    def test_load_profile_success(self):
        manager = dm.DataManager()
        test_profile = self.temp_path / "profile.json"
        test_profile.write_text(json.dumps(_sample_payload(), ensure_ascii=False), encoding="utf-8")

        data = manager.load_profile(test_profile)

        self.assertEqual(len(data["profiles"]), 1)
        self.assertEqual(data["profiles"][0]["profile_name"], "Тестовый профиль")
        self.assertIsNotNone(manager.current_data)

    def test_load_profile_invalid_root_raises(self):
        manager = dm.DataManager()
        broken = self.temp_path / "broken_root.json"
        broken.write_text(json.dumps(["not-an-object"], ensure_ascii=False), encoding="utf-8")

        with self.assertRaises(ValueError):
            manager.load_profile(broken)

    def test_load_profile_invalid_payload_raises(self):
        manager = dm.DataManager()
        broken = self.temp_path / "broken_payload.json"
        payload = _sample_payload()
        del payload["profiles"][0]["categories"][0]["items"][0]["text"]
        broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        with self.assertRaises(ValueError):
            manager.load_profile(broken)

    def test_load_active_profiles_uses_default_when_no_user_file(self):
        manager = dm.DataManager()
        data = manager.load_active_profiles()

        self.assertEqual(data["profiles"][0]["profile_name"], "Дефолт")

    def test_save_and_load_active_profiles_roundtrip(self):
        manager = dm.DataManager()
        payload = _sample_payload("Пользовательский")

        manager.save_active_profiles(payload)
        loaded = manager.load_active_profiles()

        self.assertTrue(self.user_profiles_path.exists())
        self.assertEqual(loaded["profiles"][0]["profile_name"], "Пользовательский")

    def test_save_active_profiles_rejects_non_dict(self):
        manager = dm.DataManager()
        with self.assertRaises(ValueError):
            manager.save_active_profiles([])  # type: ignore[arg-type]

    def test_load_settings_missing_returns_default(self):
        manager = dm.DataManager()
        settings = manager.load_settings()

        self.assertEqual(settings, {
            "nick": "",
            "position": "",
            "binder_enabled": False,
            "panic_hotkey": "End",
        })

    def test_load_settings_invalid_json_returns_default(self):
        manager = dm.DataManager()
        self.settings_path.write_text("{bad json", encoding="utf-8")

        settings = manager.load_settings()
        self.assertEqual(settings, {
            "nick": "",
            "position": "",
            "binder_enabled": False,
            "panic_hotkey": "End",
        })

    def test_save_and_load_settings_roundtrip(self):
        manager = dm.DataManager()
        manager.save_settings({
            "nick": "  Nick  ",
            "position": "  Medic  ",
            "binder_enabled": True,
            "panic_hotkey": "  Ctrl+Shift+F11  ",
        })

        settings = manager.load_settings()
        self.assertEqual(settings, {
            "nick": "Nick",
            "position": "Medic",
            "binder_enabled": True,
            "panic_hotkey": "Ctrl+Shift+F11",
        })

    def test_load_settings_keeps_existing_panic_hotkey(self):
        manager = dm.DataManager()
        self.settings_path.write_text(
            json.dumps(
                {
                    "nick": "Nick",
                    "position": "Medic",
                    "binder_enabled": True,
                    "panic_hotkey": "Ctrl+Shift+F12",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        settings = manager.load_settings()
        self.assertEqual(settings["panic_hotkey"], "Ctrl+Shift+F12")

    def test_item_hotkey_fields_are_normalized(self):
        manager = dm.DataManager()
        payload = _sample_payload("Нормализация")
        payload["profiles"][0]["categories"][0]["items"][0]["hotkey"] = "  Ctrl+1  "
        payload["profiles"][0]["categories"][0]["items"][0]["send_mode"] = "invalid_mode"
        payload["profiles"][0]["categories"][0]["items"][0]["enabled"] = "true"

        profile_file = self.temp_path / "normalize.json"
        profile_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        data = manager.load_profile(profile_file)
        item = data["profiles"][0]["categories"][0]["items"][0]

        self.assertTrue(isinstance(item.get("item_id"), str) and item["item_id"])
        self.assertEqual(item["hotkey"], "Ctrl+1")
        self.assertEqual(item["send_mode"], "copy")
        self.assertEqual(item["enabled"], True)

    def test_item_send_mode_paste_is_kept(self):
        manager = dm.DataManager()
        payload = _sample_payload("Режим вставки")
        payload["profiles"][0]["categories"][0]["items"][0]["send_mode"] = "paste"

        profile_file = self.temp_path / "paste_mode.json"
        profile_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        data = manager.load_profile(profile_file)
        item = data["profiles"][0]["categories"][0]["items"][0]

        self.assertEqual(item["send_mode"], "paste")

    def test_item_send_mode_paste_enter_is_kept(self):
        manager = dm.DataManager()
        payload = _sample_payload("Режим вставка+enter")
        payload["profiles"][0]["categories"][0]["items"][0]["send_mode"] = "paste_enter"
        payload["profiles"][0]["categories"][0]["items"][0]["delay_ms"] = "250"

        profile_file = self.temp_path / "paste_enter_mode.json"
        profile_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        data = manager.load_profile(profile_file)
        item = data["profiles"][0]["categories"][0]["items"][0]

        self.assertEqual(item["send_mode"], "paste_enter")
        self.assertEqual(item["delay_ms"], 250)

    def test_item_delay_ms_is_clamped(self):
        manager = dm.DataManager()
        payload = _sample_payload("Задержка")
        payload["profiles"][0]["categories"][0]["items"][0]["delay_ms"] = 999999

        profile_file = self.temp_path / "delay_clamped.json"
        profile_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        data = manager.load_profile(profile_file)
        item = data["profiles"][0]["categories"][0]["items"][0]

        self.assertEqual(item["delay_ms"], 5000)

    def test_merge_profiles_adds_new_entities_and_skips_duplicates(self):
        manager = dm.DataManager()

        current = {
            "version": "1.1",
            "profiles": [
                {
                    "profile_name": "Полиция",
                    "categories": [
                        {
                            "name": "ДПС",
                            "items": [
                                {"title": "Мегафон", "text": "/m Stop"},
                            ],
                        }
                    ],
                }
            ],
        }

        incoming = {
            "version": "1.1",
            "profiles": [
                {
                    "profile_name": "Полиция",
                    "categories": [
                        {
                            "name": "ДПС",
                            "items": [
                                {"title": "Мегафон", "text": "/m Stop"},  # duplicate
                                {"title": "Проверка", "text": "/do Проверка"},
                            ],
                        },
                        {
                            "name": "ППС",
                            "items": [
                                {"title": "Статус", "text": "/r status"},
                            ],
                        },
                    ],
                },
                {
                    "profile_name": "Медики",
                    "categories": [
                        {
                            "name": "Скорая",
                            "items": [
                                {"title": "Вызов", "text": "/r 103"},
                            ],
                        }
                    ],
                },
            ],
        }

        merged, stats = manager.merge_profiles(current, incoming)

        self.assertEqual(stats["profiles_added"], 1)
        self.assertEqual(stats["categories_added"], 2)
        self.assertEqual(stats["items_added"], 3)
        self.assertEqual(stats["items_skipped"], 1)

        self.assertEqual(len(merged["profiles"]), 2)
        police = next(p for p in merged["profiles"] if p["profile_name"] == "Полиция")
        self.assertEqual(len(police["categories"]), 2)
        dps = next(c for c in police["categories"] if c["name"] == "ДПС")
        self.assertEqual(len(dps["items"]), 2)

    def test_merge_profiles_rejects_invalid_payload(self):
        manager = dm.DataManager()
        current = _sample_payload("Current")
        invalid_incoming = {"version": "1.1", "profiles": []}

        with self.assertRaises(ValueError):
            manager.merge_profiles(current, invalid_incoming)


if __name__ == "__main__":
    unittest.main()
