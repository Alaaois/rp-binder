import copy
import json
import re
from tkinter import filedialog, messagebox

from app.constants import (
    PASTE_ENTER_DEFAULT_DELAY_MS,
    PASTE_ENTER_MAX_DELAY_MS,
    PASTE_ENTER_MIN_DELAY_MS,
)


class UIProfileContentMixin:
    @staticmethod
    def _safe_filename_part(value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            return "export"
        return re.sub(r"[\\/:*?\"<>|]+", "_", cleaned)

    @staticmethod
    def _normalize_enabled_flag(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "да"}
        return False

    @staticmethod
    def _parse_delay_ms(value) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = PASTE_ENTER_DEFAULT_DELAY_MS
        return max(PASTE_ENTER_MIN_DELAY_MS, min(PASTE_ENTER_MAX_DELAY_MS, parsed))

    def _normalize_imported_item(self, item: dict, index: int) -> dict:
        if not isinstance(item, dict):
            raise ValueError(f"Элемент #{index}: ожидается объект.")

        title = item.get("title")
        text = item.get("text")
        if not isinstance(title, str) or not isinstance(text, str):
            raise ValueError(f"Элемент #{index}: поля title и text должны быть строками.")

        normalized = dict(item)
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError(f"Элемент #{index}: title не может быть пустым.")

        normalized["title"] = normalized_title
        normalized["text"] = text

        item_id = normalized.get("item_id")
        if not isinstance(item_id, str) or not item_id.strip():
            normalized["item_id"] = self.data_manager.generate_item_id()
        else:
            normalized["item_id"] = item_id.strip()

        hotkey = normalized.get("hotkey", "")
        normalized["hotkey"] = hotkey.strip() if isinstance(hotkey, str) else ""

        send_mode = str(normalized.get("send_mode", "copy")).strip().lower()
        if send_mode not in {"copy", "paste", "paste_enter"}:
            send_mode = "copy"
        normalized["send_mode"] = send_mode

        normalized["delay_ms"] = self._parse_delay_ms(normalized.get("delay_ms", PASTE_ENTER_DEFAULT_DELAY_MS))
        normalized["enabled"] = self._normalize_enabled_flag(normalized.get("enabled", False))
        return normalized

    def _extract_import_category(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Некорректный JSON: корень файла должен быть объектом.")

        raw_category = None
        if isinstance(payload.get("category"), dict):
            raw_category = payload["category"]
        elif "name" in payload and "items" in payload:
            raw_category = payload
        elif isinstance(payload.get("profiles"), list):
            profiles = [profile for profile in payload["profiles"] if isinstance(profile, dict)]
            if not profiles:
                raise ValueError("Некорректный JSON: не найдено профилей для импорта отдела.")
            if len(profiles) > 1:
                raise ValueError("В файле несколько профилей. Для такого файла используйте импорт профилей.")
            categories = profiles[0].get("categories", [])
            if not isinstance(categories, list) or not categories:
                raise ValueError("Некорректный JSON: в профиле отсутствуют отделы.")
            if len(categories) > 1:
                raise ValueError("В файле несколько отделов. Экспортируйте один отдел или используйте импорт профилей.")
            raw_category = categories[0]

        if not isinstance(raw_category, dict):
            raise ValueError("Некорректный JSON: не найден отдел для импорта.")

        category_name = str(raw_category.get("name", "")).strip()
        if not category_name:
            raise ValueError("Некорректный JSON: у отдела отсутствует поле name.")

        raw_items = raw_category.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("Некорректный JSON: у отдела отсутствует список items.")

        normalized_items: list[dict] = []
        for index, item in enumerate(raw_items, start=1):
            normalized_items.append(self._normalize_imported_item(item, index))

        return {"name": category_name, "items": normalized_items}

    @staticmethod
    def _category_item_key(item: dict) -> tuple[str, str]:
        return (str(item.get("title", "")).strip().lower(), str(item.get("text", "")).strip().lower())

    def _merge_category_items(self, current_items: list[dict], incoming_items: list[dict]) -> tuple[int, int]:
        existing_keys = {
            self._category_item_key(item)
            for item in current_items
            if isinstance(item, dict)
        }
        added = 0
        skipped = 0
        for item in incoming_items:
            key = self._category_item_key(item)
            if key in existing_keys:
                skipped += 1
                continue
            current_items.append(copy.deepcopy(item))
            existing_keys.add(key)
            added += 1
        return added, skipped

    def _export_category_json(self):
        profile_name = self._get_selected_profile_name()
        profile = self.profiles_map.get(profile_name)
        if not profile:
            messagebox.showwarning("Экспорт отдела", "Сначала выберите профиль.", parent=self)
            return

        category_name = self._get_selected_category_name()
        category_items = self._get_selected_category_items()
        if not category_name or category_items is None:
            messagebox.showwarning("Экспорт отдела", "Сначала выберите отдел.", parent=self)
            return

        safe_profile = self._safe_filename_part(profile_name) or "profile"
        safe_category = self._safe_filename_part(category_name) or "category"
        file_path = filedialog.asksaveasfilename(
            title="Сохранить отдел",
            defaultextension=".json",
            initialfile=f"{safe_profile}__{safe_category}.json",
            filetypes=[("JSON files", "*.json")],
            parent=self
        )
        if not file_path:
            return

        payload = {
            "version": str(self.data.get("version", "1.0")) if isinstance(self.data, dict) else "1.0",
            "format": "category-pack-v1",
            "profile_name": profile_name,
            "category": {
                "name": category_name,
                "items": copy.deepcopy(category_items),
            },
        }

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            messagebox.showinfo("Экспорт отдела", f"Отдел «{category_name}» экспортирован.", parent=self)
        except Exception as error:
            messagebox.showerror("Ошибка экспорта", str(error), parent=self)

    def _import_category_json(self):
        selected_profile_name = self._get_selected_profile_name()
        profile = self.profiles_map.get(selected_profile_name)
        if not profile:
            messagebox.showwarning("Импорт отдела", "Сначала выберите профиль, в который импортировать отдел.", parent=self)
            return

        file_path = filedialog.askopenfilename(
            title="Выберите JSON отдела",
            filetypes=[("JSON files", "*.json")],
            parent=self
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            incoming_category = self._extract_import_category(payload)
        except Exception as error:
            messagebox.showerror("Ошибка импорта", str(error), parent=self)
            return

        categories = profile.get("categories")
        if not isinstance(categories, list):
            profile["categories"] = []
            categories = profile["categories"]

        category_name = incoming_category["name"]
        incoming_items = incoming_category["items"]
        target_index = None
        for index, category in enumerate(categories):
            current_name = str(category.get("name", "")).strip().lower()
            if current_name == category_name.lower():
                target_index = index
                break

        added = 0
        skipped = 0
        replaced = False
        if target_index is None:
            categories.append(copy.deepcopy(incoming_category))
            added = len(incoming_items)
        else:
            mode_choice = messagebox.askyesnocancel(
                "Импорт отдела",
                f"Отдел «{category_name}» уже существует в текущем профиле.\n\n"
                "Да — заменить отдел целиком\n"
                "Нет — объединить фразы (без дублей)\n"
                "Отмена — отменить импорт.",
                parent=self,
            )
            if mode_choice is None:
                return

            if mode_choice:
                categories[target_index] = copy.deepcopy(incoming_category)
                replaced = True
                added = len(incoming_items)
            else:
                target_items = categories[target_index].get("items")
                if not isinstance(target_items, list):
                    categories[target_index]["items"] = []
                    target_items = categories[target_index]["items"]
                added, skipped = self._merge_category_items(target_items, incoming_items)

        saved = self._persist_profiles()
        if not saved:
            return

        self._apply_profiles_payload(self.data, preferred_profile_name=selected_profile_name)
        self._select_category_by_name(category_name)

        if replaced:
            messagebox.showinfo(
                "Импорт отдела",
                f"Отдел «{category_name}» заменен.\nФраз в отделе: {added}.",
                parent=self,
            )
        elif target_index is None:
            messagebox.showinfo(
                "Импорт отдела",
                f"Отдел «{category_name}» импортирован.\nДобавлено фраз: {added}.",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "Импорт отдела",
                f"Отдел «{category_name}» объединен.\n"
                f"Добавлено фраз: {added}\n"
                f"Пропущено дублей: {skipped}",
                parent=self,
            )

    def _collect_item_variables(self, item: dict, text: str) -> list[str]:
        variables: list[str] = []

        declared = item.get("variables", [])
        if isinstance(declared, list):
            for var_name in declared:
                if not isinstance(var_name, str):
                    continue
                clean_name = var_name.strip()
                if clean_name and clean_name not in variables:
                    variables.append(clean_name)

        found = re.findall(r"\{([^{}]+)\}", text)
        for var_name in found:
            clean_name = var_name.strip()
            if clean_name and clean_name not in variables:
                variables.append(clean_name)

        return variables

    def _ask_variables_values(self, variables: list[str]) -> dict[str, str] | None:
        values: dict[str, str] = {}

        for var_name in variables:
            auto_value = self._get_auto_value_for_variable(var_name)
            if auto_value:
                values[var_name] = auto_value
                continue

            while True:
                value = self._ask_input_dialog(
                    "Подстановка переменных",
                    f"Введите значение для {{{var_name}}}:"
                )

                if value is None:
                    return None

                value = value.strip()
                if value:
                    values[var_name] = value
                    break

                messagebox.showwarning(
                    "Пустое значение",
                    f"Поле {{{var_name}}} не может быть пустым.",
                    parent=self
                )

        return values

    def _get_auto_value_for_variable(self, var_name: str) -> str:
        normalized = re.sub(r"[\s_\-]+", "", var_name.strip().lower())
        nick = self.user_settings.get("nick", "").strip()
        position = self.user_settings.get("position", "").strip()

        nick_aliases = {"nick", "nickname", "ник", "никнейм"}
        position_aliases = {"position", "role", "rank", "должность", "роль", "звание"}

        if normalized in nick_aliases:
            return nick
        if normalized in position_aliases:
            return position
        return ""

    def _render_item_text(self, item: dict) -> str | None:
        text = item.get("text", "")
        if not text:
            return ""

        variables = self._collect_item_variables(item, text)
        if not variables:
            return text

        values = self._ask_variables_values(variables)
        if values is None:
            self._set_status("Копирование отменено")
            return None

        for var_name, value in values.items():
            text = text.replace(f"{{{var_name}}}", value)

        return text

    def _apply_filter(self):
        query = self.search_var.get().strip().lower()

        cat_selection = self.category_listbox.curselection()
        if not cat_selection:
            return

        category_name = self.category_listbox.get(cat_selection[0])
        source_items = self.category_map.get(category_name, [])

        if not query:
            self._fill_items(source_items)
            return

        filtered = []
        for item in source_items:
            title = item.get("title", "").lower()
            text = item.get("text", "").lower()
            if query in title or query in text:
                filtered.append(item)

        self._fill_items(filtered)

    def _import_json(self):
        file_path = filedialog.askopenfilename(
            title="Выберите JSON профиль",
            filetypes=[("JSON files", "*.json")],
            parent=self
        )
        if not file_path:
            return

        mode_choice = messagebox.askyesnocancel(
            "Режим импорта",
            "Выберите режим импорта:\n\n"
            "Да — заменить текущие профили\n"
            "Нет — объединить с текущими профилями\n"
            "Отмена — отменить импорт.",
            parent=self
        )
        if mode_choice is None:
            return

        selected_profile_name = self._get_selected_profile_name()

        try:
            incoming_data = self.data_manager.import_profile(file_path)

            if mode_choice is True:
                data = incoming_data
                self._apply_profiles_payload(data)
                self._persist_profiles()

                profiles_count = len(data.get("profiles", []))
                messagebox.showinfo(
                    "Импорт",
                    f"Импорт (замена) выполнен.\nЗагружено профилей: {profiles_count}.",
                    parent=self
                )
                return

            base_data = self.data if isinstance(self.data, dict) else {"version": "1.0", "profiles": []}
            merged_data, stats = self.data_manager.merge_profiles(base_data, incoming_data)
            self._apply_profiles_payload(merged_data, preferred_profile_name=selected_profile_name)
            self._persist_profiles()

            messagebox.showinfo(
                "Импорт",
                "Импорт (объединение) выполнен.\n\n"
                f"Добавлено профилей: {stats['profiles_added']}\n"
                f"Добавлено отделов: {stats['categories_added']}\n"
                f"Добавлено фраз: {stats['items_added']}\n"
                f"Пропущено дублей фраз: {stats['items_skipped']}",
                parent=self
            )
        except Exception as error:
            messagebox.showerror("Ошибка импорта", str(error), parent=self)

    def _export_profile(self):
        selected_name = self._get_selected_profile_name()
        profile = self.profiles_map.get(selected_name)
        if not profile:
            messagebox.showwarning("Экспорт", "Сначала выберите профиль для экспорта.", parent=self)
            return

        safe_name = selected_name.replace("/", "_").replace("\\", "_").strip() or "profile"
        file_path = filedialog.asksaveasfilename(
            title="Сохранить профиль",
            defaultextension=".json",
            initialfile=f"{safe_name}.json",
            filetypes=[("JSON files", "*.json")],
            parent=self
        )
        if not file_path:
            return

        payload = {
            "version": str(self.data.get("version", "1.0")) if isinstance(self.data, dict) else "1.0",
            "profiles": [profile],
        }

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            messagebox.showinfo("Экспорт", "Профиль успешно экспортирован.", parent=self)
        except Exception as error:
            messagebox.showerror("Ошибка экспорта", str(error), parent=self)
