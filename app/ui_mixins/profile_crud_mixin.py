import tkinter as tk
from tkinter import messagebox

from app.constants import CHAT_OPEN_DELAY_DEFAULT_MS, CHAT_OPEN_HOTKEY_DEFAULT, PASTE_ENTER_DEFAULT_DELAY_MS


class UIProfileCrudMixin:
    def _persist_profiles(self, refresh_hotkeys: bool = True) -> bool:
        if not isinstance(self.data, dict):
            return False

        try:
            self.data_manager.save_active_profiles(self.data)
            if refresh_hotkeys:
                self._refresh_hotkeys(show_errors=False)
            return True
        except Exception as error:
            messagebox.showwarning(
                "Сохранение профилей",
                f"Не удалось сохранить профили.\n{error}",
                parent=self
            )
            return False

    def _get_selected_profile_name(self) -> str:
        value = self.profile_selector.get().strip()
        return "" if value == "-" else value

    def _get_selected_profile_and_index(self) -> tuple[dict | None, int | None]:
        if not isinstance(self.data, dict):
            return None, None

        selected_name = self._get_selected_profile_name()
        profile = self.profiles_map.get(selected_name)
        if not profile:
            return None, None

        profiles = self.data.get("profiles", [])
        if not isinstance(profiles, list):
            return None, None

        for index, current in enumerate(profiles):
            if current is profile:
                return profile, index

        for index, current in enumerate(profiles):
            if current == profile:
                return profile, index

        return profile, None

    def _profile_name_exists(self, profile_name: str, exclude_index: int | None = None) -> bool:
        if not isinstance(self.data, dict):
            return False

        profiles = self.data.get("profiles", [])
        if not isinstance(profiles, list):
            return False

        needle = profile_name.strip().lower()
        for index, profile in enumerate(profiles):
            if exclude_index is not None and index == exclude_index:
                continue
            current_name = str(profile.get("profile_name", "")).strip().lower()
            if current_name == needle:
                return True
        return False

    def _add_profile(self):
        if not isinstance(self.data, dict):
            messagebox.showwarning("Профили", "Данные профилей не загружены.", parent=self)
            return

        new_name = self._ask_required_text("Новый профиль", "Введите название профиля:")
        if new_name is None:
            return

        if self._profile_name_exists(new_name):
            messagebox.showwarning("Профили", "Профиль с таким названием уже существует.", parent=self)
            return

        profiles = self.data.setdefault("profiles", [])
        if not isinstance(profiles, list):
            messagebox.showerror("Профили", "Некорректная структура профилей.", parent=self)
            return

        profiles.append({"profile_name": new_name, "categories": []})
        self._persist_profiles()
        self._apply_profiles_payload(self.data, preferred_profile_name=new_name)

    def _rename_profile(self):
        profile, profile_index = self._get_selected_profile_and_index()
        if not profile:
            messagebox.showwarning("Профили", "Сначала выберите профиль.", parent=self)
            return

        current_name = str(profile.get("profile_name", "")).strip()
        new_name = self._ask_required_text(
            "Переименовать профиль",
            f"Введите новое название профиля:\nТекущее значение: {current_name or '-'}"
        )
        if new_name is None:
            return
        if new_name == current_name:
            return

        if self._profile_name_exists(new_name, exclude_index=profile_index):
            messagebox.showwarning("Профили", "Профиль с таким названием уже существует.", parent=self)
            return

        profile["profile_name"] = new_name
        self._persist_profiles()
        self._apply_profiles_payload(self.data, preferred_profile_name=new_name)

    def _delete_profile(self):
        profile, profile_index = self._get_selected_profile_and_index()
        if profile is None or profile_index is None:
            messagebox.showwarning("Профили", "Сначала выберите профиль.", parent=self)
            return

        profiles = self.data.get("profiles", []) if isinstance(self.data, dict) else []
        if not isinstance(profiles, list) or len(profiles) <= 1:
            messagebox.showwarning("Профили", "Нельзя удалить последний профиль.", parent=self)
            return

        profile_name = str(profile.get("profile_name", "Без названия"))
        confirm = messagebox.askyesno(
            "Удаление профиля",
            f"Удалить профиль «{profile_name}»?",
            parent=self
        )
        if not confirm:
            return

        del profiles[profile_index]
        self._persist_profiles()

        preferred_name = str(profiles[min(profile_index, len(profiles) - 1)].get("profile_name", "")).strip()
        self._apply_profiles_payload(self.data, preferred_profile_name=preferred_name)

    def _get_current_categories(self) -> list[dict]:
        if not isinstance(self.profile, dict):
            return []

        categories = self.profile.get("categories")
        if isinstance(categories, list):
            return categories

        self.profile["categories"] = []
        return self.profile["categories"]

    def _get_selected_category_name(self) -> str | None:
        selection = self.category_listbox.curselection()
        if not selection:
            return None
        return self.category_listbox.get(selection[0])

    def _find_category_index(self, category_name: str) -> int | None:
        categories = self._get_current_categories()
        for index, category in enumerate(categories):
            if str(category.get("name", "")) == category_name:
                return index
        return None

    def _category_name_exists(self, category_name: str, exclude_index: int | None = None) -> bool:
        needle = category_name.strip().lower()
        categories = self._get_current_categories()
        for index, category in enumerate(categories):
            if exclude_index is not None and index == exclude_index:
                continue
            current_name = str(category.get("name", "")).strip().lower()
            if current_name == needle:
                return True
        return False

    def _select_category_by_index(self, index: int):
        if self.category_listbox.size() == 0:
            return
        if index < 0 or index >= self.category_listbox.size():
            return

        self.category_listbox.selection_clear(0, tk.END)
        self.category_listbox.selection_set(index)
        self.category_listbox.activate(index)
        self._on_category_selected()

    def _select_category_by_name(self, category_name: str):
        for index in range(self.category_listbox.size()):
            if self.category_listbox.get(index) == category_name:
                self._select_category_by_index(index)
                return

    def _get_selected_category_items(self) -> list[dict] | None:
        category_name = self._get_selected_category_name()
        if not category_name:
            return None

        categories = self._get_current_categories()
        for category in categories:
            if str(category.get("name", "")) != category_name:
                continue

            items = category.get("items")
            if isinstance(items, list):
                return items

            category["items"] = []
            return category["items"]
        return None

    def _find_item_index_in_source(self, source_items: list[dict], item: dict) -> int | None:
        for index, current in enumerate(source_items):
            if current is item:
                return index
        for index, current in enumerate(source_items):
            if current == item:
                return index
        return None

    def _select_filtered_item(self, item: dict):
        for index, current in enumerate(self.filtered_items):
            if current is item:
                self.items_listbox.selection_clear(0, tk.END)
                self.items_listbox.selection_set(index)
                self.items_listbox.activate(index)
                self._on_item_selected()
                return

    def _add_category(self):
        if not isinstance(self.profile, dict):
            messagebox.showwarning("Отделы", "Сначала выберите профиль.", parent=self)
            return

        category_name = self._ask_required_text("Новый отдел", "Введите название отдела:")
        if category_name is None:
            return
        if self._category_name_exists(category_name):
            messagebox.showwarning("Отделы", "Отдел с таким названием уже существует.", parent=self)
            return

        categories = self._get_current_categories()
        categories.append({"name": category_name, "items": []})
        self._persist_profiles()
        self._apply_profile(self.profile)
        self._select_category_by_name(category_name)

    def _rename_category(self):
        category_name = self._get_selected_category_name()
        if not category_name:
            messagebox.showwarning("Отделы", "Сначала выберите отдел.", parent=self)
            return

        category_index = self._find_category_index(category_name)
        if category_index is None:
            return

        new_name = self._ask_required_text(
            "Переименовать отдел",
            f"Введите новое название отдела:\nТекущее значение: {category_name}"
        )
        if new_name is None:
            return
        if new_name == category_name:
            return
        if self._category_name_exists(new_name, exclude_index=category_index):
            messagebox.showwarning("Отделы", "Отдел с таким названием уже существует.", parent=self)
            return

        categories = self._get_current_categories()
        categories[category_index]["name"] = new_name
        self._persist_profiles()
        self._apply_profile(self.profile)
        self._select_category_by_name(new_name)

    def _delete_category(self):
        category_name = self._get_selected_category_name()
        if not category_name:
            messagebox.showwarning("Отделы", "Сначала выберите отдел.", parent=self)
            return

        category_index = self._find_category_index(category_name)
        if category_index is None:
            return

        confirm = messagebox.askyesno(
            "Удаление отдела",
            f"Удалить отдел «{category_name}»?",
            parent=self
        )
        if not confirm:
            return

        categories = self._get_current_categories()
        del categories[category_index]
        self._persist_profiles()
        self._apply_profile(self.profile)

        if self.category_listbox.size() > 0:
            next_index = min(category_index, self.category_listbox.size() - 1)
            self._select_category_by_index(next_index)

    def _add_item(self):
        source_items = self._get_selected_category_items()
        if source_items is None:
            messagebox.showwarning("Фразы", "Сначала выберите отдел.", parent=self)
            return

        title = self._ask_required_text("Новая фраза", "Введите название фразы:")
        if title is None:
            return

        text = self._ask_required_text("Новая фраза", "Введите текст фразы:")
        if text is None:
            return

        item = {
            "item_id": self.data_manager.generate_item_id(),
            "title": title,
            "text": text,
            "hotkey": "",
            "enabled": False,
            "send_mode": "copy",
            "delay_ms": PASTE_ENTER_DEFAULT_DELAY_MS,
            "chat_open_hotkey": CHAT_OPEN_HOTKEY_DEFAULT,
            "chat_open_delay_ms": CHAT_OPEN_DELAY_DEFAULT_MS,
            "chat_send_each_line": False,
        }
        source_items.append(item)
        self._persist_profiles()
        self._on_category_selected()
        self._apply_filter()
        self._select_filtered_item(item)

    def _edit_item(self):
        if not self.selected_item:
            messagebox.showwarning("Фразы", "Сначала выберите фразу.", parent=self)
            return

        source_items = self._get_selected_category_items()
        if source_items is None:
            messagebox.showwarning("Фразы", "Сначала выберите отдел.", parent=self)
            return

        item_index = self._find_item_index_in_source(source_items, self.selected_item)
        if item_index is None:
            messagebox.showwarning("Фразы", "Не удалось найти выбранную фразу.", parent=self)
            return

        current_item = source_items[item_index]
        current_title = str(current_item.get("title", "")).strip()
        current_text = str(current_item.get("text", "")).strip()

        new_title = self._ask_required_text(
            "Редактировать фразу",
            f"Введите новое название:\nТекущее значение: {current_title or '-'}"
        )
        if new_title is None:
            return

        new_text = self._ask_required_text(
            "Редактировать фразу",
            f"Введите новый текст:\nТекущее значение: {current_text or '-'}"
        )
        if new_text is None:
            return

        current_item["title"] = new_title
        current_item["text"] = new_text
        self._persist_profiles()
        self._on_category_selected()
        self._apply_filter()
        self._select_filtered_item(current_item)

    def _delete_item(self):
        if not self.selected_item:
            messagebox.showwarning("Фразы", "Сначала выберите фразу.", parent=self)
            return

        source_items = self._get_selected_category_items()
        if source_items is None:
            messagebox.showwarning("Фразы", "Сначала выберите отдел.", parent=self)
            return

        item_index = self._find_item_index_in_source(source_items, self.selected_item)
        if item_index is None:
            messagebox.showwarning("Фразы", "Не удалось найти выбранную фразу.", parent=self)
            return

        item_title = str(source_items[item_index].get("title", "Без названия"))
        confirm = messagebox.askyesno(
            "Удаление фразы",
            f"Удалить фразу «{item_title}»?",
            parent=self
        )
        if not confirm:
            return

        del source_items[item_index]
        self._persist_profiles()
        self._on_category_selected()
        self._apply_filter()
        if self.items_listbox.size() > 0:
            self.items_listbox.selection_clear(0, tk.END)
            self.items_listbox.selection_set(0)
            self.items_listbox.activate(0)
            self._on_item_selected()

    def _load_startup_profiles(self):
        try:
            data = self.data_manager.load_active_profiles()
            self._apply_profiles_payload(data)
        except Exception as error:
            try:
                data = self.data_manager.load_default_profile()
                self._apply_profiles_payload(data)
                messagebox.showwarning(
                    "Ошибка загрузки профилей",
                    f"Не удалось загрузить сохраненные профили.\nЗагружен дефолтный набор.\n\n{error}",
                    parent=self
                )
            except Exception as fallback_error:
                messagebox.showerror("Ошибка", f"Не удалось загрузить профили:\n{fallback_error}", parent=self)

    def _make_unique_profile_name(self, base_name: str) -> str:
        if base_name not in self.profiles_map:
            return base_name

        idx = 2
        while True:
            candidate = f"{base_name} ({idx})"
            if candidate not in self.profiles_map:
                return candidate
            idx += 1

    def _apply_profiles_payload(self, data: dict, preferred_profile_name: str | None = None):
        self.data = data
        self.profiles_map.clear()

        profile_names: list[str] = []
        for index, profile in enumerate(data.get("profiles", []), start=1):
            raw_name = profile.get("profile_name", "").strip()
            base_name = raw_name if raw_name else f"Профиль {index}"
            unique_name = self._make_unique_profile_name(base_name)
            self.profiles_map[unique_name] = profile
            profile_names.append(unique_name)

        if not profile_names:
            raise ValueError("В JSON не найдено ни одного профиля")

        self.profile_selector.configure(values=profile_names)
        selected_name = profile_names[0]
        if preferred_profile_name and preferred_profile_name in self.profiles_map:
            selected_name = preferred_profile_name

        self.profile_selector.set(selected_name)
        self._on_profile_changed(selected_name)
        self._refresh_hotkeys(show_errors=False)

    def _on_profile_changed(self, selected_profile_name: str):
        profile = self.profiles_map.get(selected_profile_name)
        if not profile:
            return

        self.profile = profile
        self._apply_profile(profile)
        if not self.category_listbox.curselection():
            self._refresh_hotkeys(show_errors=False)

    def _apply_profile(self, profile: dict):
        self.category_map.clear()
        self.category_listbox.delete(0, tk.END)
        self.items_listbox.delete(0, tk.END)
        self.filtered_items.clear()
        self.selected_item = None
        self._set_preview("Выбери категорию")

        for category in profile.get("categories", []):
            name = category["name"]
            items = category["items"]
            self.category_map[name] = items
            self.category_listbox.insert(tk.END, name)

        if self.category_listbox.size() > 0:
            self.category_listbox.selection_set(0)
            self._on_category_selected()

    def _on_category_selected(self, event=None):
        selection = self.category_listbox.curselection()
        if not selection:
            self._refresh_hotkeys(show_errors=False)
            return

        category_name = self.category_listbox.get(selection[0])
        items = self.category_map.get(category_name, [])
        self._fill_items(items)
        if self.search_var.get().strip():
            self._apply_filter()
        self._refresh_hotkeys(show_errors=False)

    def _fill_items(self, items: list[dict]):
        self.items_listbox.delete(0, tk.END)
        self.filtered_items = items[:]

        conflicts: dict[int, str] = {}
        get_conflicts = getattr(self, "_get_scope_hotkey_conflicts", None)
        if callable(get_conflicts):
            try:
                conflicts = get_conflicts()
            except Exception:
                conflicts = {}

        for index, item in enumerate(self.filtered_items):
            title = str(item.get("title", "Без названия"))
            conflict_hotkey = conflicts.get(id(item))
            if conflict_hotkey:
                display_title = f"[КОНФЛИКТ {conflict_hotkey}] {title}"
            else:
                display_title = title
            self.items_listbox.insert(tk.END, display_title)
            if conflict_hotkey:
                try:
                    self.items_listbox.itemconfig(index, fg="#d35400")
                except Exception:
                    pass

        self.selected_item = None
        self._set_preview("Выбери фразу")
        self._update_bind_item_status()

    def _refresh_items_bind_highlight(self):
        current_item = self.selected_item
        if self.search_var.get().strip():
            self._apply_filter()
        else:
            source_items = self._get_selected_category_items()
            self._fill_items(source_items if isinstance(source_items, list) else [])
        if isinstance(current_item, dict):
            self._select_filtered_item(current_item)

    def _on_item_selected(self, event=None):
        selection = self.items_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self.filtered_items):
            return

        self.selected_item = self.filtered_items[idx]
        self._set_preview(self.selected_item.get("text", ""))
        self._update_bind_item_status()

    def _set_preview(self, text: str):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")
        self._refresh_line_numbers()

    def _copy_selected_text(self):
        if not self.selected_item:
            return

        text = self._render_item_text(self.selected_item)
        if text is None:
            return
        if not text:
            return

        self._copy_text_to_clipboard(text)
