import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app.constants import PANIC_HOTKEY_DEFAULT, STATUS_MESSAGE_MS


class UIEditorMixin:
    def _copy_preview_selection(self, _event=None):
        try:
            selected_text = self.preview_text._textbox.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"

        self.clipboard_clear()
        self.clipboard_append(selected_text)
        self._set_status("Выделенный текст скопирован ✅")
        return "break"

    def _select_all_preview_text(self, _event=None):
        textbox = self.preview_text._textbox
        textbox.tag_add("sel", "1.0", "end-1c")
        textbox.mark_set("insert", "1.0")
        textbox.see("insert")
        return "break"

    def _update_user_label(self):
        nick = self.user_settings.get("nick", "").strip()
        position = self.user_settings.get("position", "").strip()

        if nick and position:
            self.user_label.configure(text=f"Пользователь: {nick} ({position})")
        else:
            self.user_label.configure(text="Пользователь: -")

    def _set_status(self, text: str, duration_ms: int | None = STATUS_MESSAGE_MS):
        self.copy_status.configure(text=text)
        if duration_ms and text:
            self.after(duration_ms, lambda: self.copy_status.configure(text=""))

    def _ask_input_dialog(self, title: str, text: str) -> str | None:
        dialog = ctk.CTkInputDialog(title=title, text=text)
        dialog.after(10, lambda d=dialog: self._center_popup(d))
        return dialog.get_input()

    def _iter_all_items(self):
        if not isinstance(self.data, dict):
            return

        profiles = self.data.get("profiles", [])
        if not isinstance(profiles, list):
            return

        for profile in profiles:
            categories = profile.get("categories", [])
            if not isinstance(categories, list):
                continue
            for category in categories:
                items = category.get("items", [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict):
                        yield item

    def _set_inline_edit_controls(self, editing: bool):
        self.inline_edit_mode = editing
        for control, enabled_state in self._disabled_while_editing:
            control.configure(state="disabled" if editing else enabled_state)
        for control, enabled_state in self._enabled_while_editing:
            control.configure(state=enabled_state if editing else "disabled")

        if editing:
            self._set_status("Режим редактирования", duration_ms=None)
        else:
            self._set_status("")

    def _start_inline_edit(self):
        if self.inline_edit_mode:
            return
        if not self.selected_item:
            messagebox.showwarning("Редактирование", "Сначала выберите фразу.", parent=self)
            return

        self.inline_edit_item = self.selected_item
        text = str(self.inline_edit_item.get("text", ""))
        self._set_inline_edit_controls(True)
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        self._refresh_line_numbers()
        self.preview_text.focus_set()

    def _cancel_inline_edit(self):
        if not self.inline_edit_mode:
            return

        self.inline_edit_item = None
        self._set_inline_edit_controls(False)
        if self.selected_item:
            self._set_preview(self.selected_item.get("text", ""))
        else:
            self._set_preview("Выбери фразу")

    def _save_inline_edit(self):
        if not self.inline_edit_mode or not isinstance(self.inline_edit_item, dict):
            return

        text = self.preview_text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showwarning("Редактирование", "Текст фразы не может быть пустым.", parent=self)
            return

        self.inline_edit_item["text"] = text
        self.selected_item = self.inline_edit_item
        saved = self._persist_profiles()

        self._set_inline_edit_controls(False)
        self._set_preview(text)
        if saved:
            self._set_status("Сохранено ✅")
        self.inline_edit_item = None

    def _ask_required_text(self, title: str, label: str) -> str | None:
        while True:
            value = self._ask_input_dialog(title, label)

            if value is None:
                return None

            value = value.strip()
            if value:
                return value

            messagebox.showwarning("Пустое значение", "Это поле обязательно для заполнения.", parent=self)

    def _ensure_registration(self) -> bool:
        settings = self.data_manager.load_settings()
        nick = settings.get("nick", "").strip()
        position = settings.get("position", "").strip()
        binder_enabled = bool(settings.get("binder_enabled", False))
        panic_hotkey = str(settings.get("panic_hotkey", PANIC_HOTKEY_DEFAULT)).strip() or PANIC_HOTKEY_DEFAULT

        if nick and position:
            self.user_settings = {
                "nick": nick,
                "position": position,
                "binder_enabled": binder_enabled,
                "panic_hotkey": panic_hotkey,
            }
            self._update_user_label()
            return True

        messagebox.showinfo(
            "Первый запуск",
            "Заполните ник и должность.\nЭто нужно один раз при первом запуске.",
            parent=self
        )

        while True:
            nick = self._ask_required_text("Регистрация", "Введите ваш ник:")
            if nick is None:
                close_app = messagebox.askyesno(
                    "Отмена регистрации",
                    "Без регистрации приложение закроется.\nЗакрыть приложение?",
                    parent=self
                )
                if close_app:
                    return False
                continue

            position = self._ask_required_text("Регистрация", "Введите вашу должность:")
            if position is None:
                close_app = messagebox.askyesno(
                    "Отмена регистрации",
                    "Без регистрации приложение закроется.\nЗакрыть приложение?",
                    parent=self
                )
                if close_app:
                    return False
                continue

            self.user_settings = {
                "nick": nick,
                "position": position,
                "binder_enabled": bool(self.user_settings.get("binder_enabled", False)),
                "panic_hotkey": str(self.user_settings.get("panic_hotkey", PANIC_HOTKEY_DEFAULT)).strip() or PANIC_HOTKEY_DEFAULT,
            }
            self._update_user_label()

            try:
                self.data_manager.save_settings(self.user_settings)
            except Exception as error:
                messagebox.showwarning(
                    "Ошибка сохранения",
                    f"Не удалось сохранить данные регистрации.\n{error}",
                    parent=self
                )
            return True

    def _edit_user_settings(self):
        current_nick = self.user_settings.get("nick", "").strip()
        current_position = self.user_settings.get("position", "").strip()

        nick = self._ask_required_text(
            "Изменить данные",
            f"Введите ваш ник:\nТекущее значение: {current_nick or '-'}"
        )
        if nick is None:
            return

        position = self._ask_required_text(
            "Изменить данные",
            f"Введите вашу должность:\nТекущее значение: {current_position or '-'}"
        )
        if position is None:
            return

        self.user_settings = {
            "nick": nick,
            "position": position,
            "binder_enabled": bool(self.user_settings.get("binder_enabled", False)),
            "panic_hotkey": str(self.user_settings.get("panic_hotkey", PANIC_HOTKEY_DEFAULT)).strip() or PANIC_HOTKEY_DEFAULT,
        }
        self._update_user_label()
        try:
            self.data_manager.save_settings(self.user_settings)
            messagebox.showinfo("Готово", "Данные пользователя обновлены.", parent=self)
        except Exception as error:
            messagebox.showwarning(
                "Ошибка сохранения",
                f"Не удалось сохранить данные пользователя.\n{error}",
                parent=self
            )
