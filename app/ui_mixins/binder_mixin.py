import ctypes
import platform
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app.binder import normalize_hotkey
from app.clipboard import copy_to_clipboard, paste_text_to_active_window
from app.constants import (
    PANIC_HOTKEY_DEFAULT,
    PASTE_ENTER_DEFAULT_DELAY_MS,
    PASTE_ENTER_MAX_DELAY_MS,
    PASTE_ENTER_MIN_DELAY_MS,
)


class UIBinderMixin:
    PANIC_ITEM_ID = "__panic__"

    @staticmethod
    def _parse_delay_ms(value: str | int | float | None) -> int:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except Exception:
            parsed = PASTE_ENTER_DEFAULT_DELAY_MS
        return max(PASTE_ENTER_MIN_DELAY_MS, min(PASTE_ENTER_MAX_DELAY_MS, parsed))

    def _get_panic_hotkey(self) -> str:
        raw_value = str(self.user_settings.get("panic_hotkey", PANIC_HOTKEY_DEFAULT)).strip() or PANIC_HOTKEY_DEFAULT
        try:
            return normalize_hotkey(raw_value)
        except ValueError:
            return PANIC_HOTKEY_DEFAULT

    @staticmethod
    def _keysym_to_hotkey_token(keysym: str) -> str | None:
        key = (keysym or "").strip()
        if not key:
            return None

        modifiers = {
            "Shift_L", "Shift_R",
            "Control_L", "Control_R",
            "Alt_L", "Alt_R",
            "Meta_L", "Meta_R",
            "Super_L", "Super_R",
            "Win_L", "Win_R",
        }
        if key in modifiers:
            return None

        special_map = {
            "Return": "Enter",
            "Escape": "Esc",
            "BackSpace": "Backspace",
            "Delete": "Delete",
            "Insert": "Insert",
            "Home": "Home",
            "End": "End",
            "Prior": "PageUp",
            "Next": "PageDown",
            "Up": "Up",
            "Down": "Down",
            "Left": "Left",
            "Right": "Right",
            "Tab": "Tab",
            "space": "Space",
            "KP_Add": "NumPlus",
            "KP_Subtract": "NumMinus",
            "KP_Multiply": "NumMultiply",
            "KP_Divide": "NumDivide",
            "KP_Decimal": "NumDecimal",
            "KP_Enter": "NumEnter",
            "KP_Insert": "Num0",
            "KP_End": "Num1",
            "KP_Down": "Num2",
            "KP_Next": "Num3",
            "KP_Left": "Num4",
            "KP_Begin": "Num5",
            "KP_Right": "Num6",
            "KP_Home": "Num7",
            "KP_Up": "Num8",
            "KP_Prior": "Num9",
        }
        if key in special_map:
            return special_map[key]

        if key.startswith("KP_") and len(key) == 4 and key[-1].isdigit():
            return f"Num{key[-1]}"

        if len(key) == 1 and key.isalpha():
            return key.upper()
        if len(key) == 1 and key.isdigit():
            return key

        upper = key.upper()
        if upper.startswith("F") and upper[1:].isdigit():
            number = int(upper[1:])
            if 1 <= number <= 24:
                return f"F{number}"

        return None

    @staticmethod
    def _keycode_to_numpad_token(keycode: int) -> str | None:
        # Windows virtual-key codes для numpad.
        mapping = {
            96: "Num0",
            97: "Num1",
            98: "Num2",
            99: "Num3",
            100: "Num4",
            101: "Num5",
            102: "Num6",
            103: "Num7",
            104: "Num8",
            105: "Num9",
            106: "NumMultiply",
            107: "NumPlus",
            109: "NumMinus",
            110: "NumDecimal",
            111: "NumDivide",
        }
        return mapping.get(keycode)

    @staticmethod
    def _modifier_parts_from_event(event: tk.Event) -> list[str]:
        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                parts: list[str] = []
                if user32.GetAsyncKeyState(0x11) & 0x8000:
                    parts.append("Ctrl")
                if user32.GetAsyncKeyState(0x12) & 0x8000:
                    parts.append("Alt")
                if user32.GetAsyncKeyState(0x10) & 0x8000:
                    parts.append("Shift")
                if (user32.GetAsyncKeyState(0x5B) & 0x8000) or (user32.GetAsyncKeyState(0x5C) & 0x8000):
                    parts.append("Win")
                return parts
            except Exception:
                pass

        state = int(getattr(event, "state", 0))
        parts: list[str] = []
        if state & 0x0004:
            parts.append("Ctrl")
        if state & 0x0008:
            parts.append("Alt")
        if state & 0x0001:
            parts.append("Shift")
        if state & 0x0040:
            parts.append("Win")
        return parts

    def _build_hotkey_from_event(self, event: tk.Event) -> str | None:
        key_token = self._keycode_to_numpad_token(int(getattr(event, "keycode", 0)))
        if not key_token:
            key_token = self._keysym_to_hotkey_token(getattr(event, "keysym", ""))
        if not key_token:
            return None

        parts = self._modifier_parts_from_event(event)
        parts.append(key_token)
        return "+".join(parts)

    def _capture_hotkey(self, current_hotkey: str) -> str | None:
        result: dict[str, str | None] = {"value": None}
        resume_binds_after_capture = bool(self._binds_enabled)

        if resume_binds_after_capture:
            self._hotkeys_temporarily_suspended = True
            self._hotkeys_manager.stop()
            self._set_status("PANIC: бинды временно отключены для записи хоткея", duration_ms=None)

        try:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Назначение бинда")
            dialog.resizable(False, False)
            dialog.transient(self)

            frame = ctk.CTkFrame(dialog)
            frame.pack(fill="both", expand=True, padx=12, pady=12)

            current_label = current_hotkey or "-"
            ctk.CTkLabel(
                frame,
                text=(
                    "Нажмите желаемую клавишу/комбинацию.\n"
                    "Примеры: End, Ctrl+2, Alt+F3.\n"
                    f"Текущий бинд: {current_label}"
                ),
                justify="left",
            ).pack(anchor="w", pady=(0, 10))

            preview_var = tk.StringVar(value="Ожидание нажатия...")
            ctk.CTkLabel(frame, textvariable=preview_var, anchor="w").pack(fill="x", pady=(0, 10))

            actions = ctk.CTkFrame(frame, fg_color="transparent")
            actions.pack(fill="x")
            actions.grid_columnconfigure(0, weight=1)
            actions.grid_columnconfigure(1, weight=1)
            actions.grid_columnconfigure(2, weight=1)

            def close_with(value: str | None):
                result["value"] = value
                try:
                    dialog.grab_release()
                except Exception:
                    pass
                dialog.destroy()

            def on_key_press(event: tk.Event):
                raw_hotkey = self._build_hotkey_from_event(event)
                if not raw_hotkey:
                    return "break"
                try:
                    normalized = normalize_hotkey(raw_hotkey)
                except ValueError:
                    return "break"
                preview_var.set(normalized)
                close_with(normalized)
                return "break"

            ctk.CTkButton(actions, text="Сбросить", command=lambda: close_with("")).grid(row=0, column=0, padx=(0, 6), sticky="ew")
            ctk.CTkButton(actions, text="Отмена", command=lambda: close_with(None)).grid(row=0, column=1, padx=3, sticky="ew")
            ctk.CTkButton(actions, text="Оставить", command=lambda: close_with(current_hotkey or None)).grid(row=0, column=2, padx=(6, 0), sticky="ew")

            dialog.bind("<KeyPress>", on_key_press)
            dialog.focus_force()
            dialog.grab_set()
            self._center_popup(dialog, fallback_width=420, fallback_height=180)
            dialog.wait_window()
        finally:
            if resume_binds_after_capture:
                self._hotkeys_temporarily_suspended = False
                if self._binds_enabled:
                    self._refresh_hotkeys(show_errors=False)
                    self._set_status("Бинды восстановлены")
                else:
                    self._set_status("")

        return result["value"]

    def _set_binds_switch_state(self, enabled: bool, persist: bool = True):
        requested = bool(enabled)
        self._binds_enabled = requested and self._hotkeys_manager.is_supported
        if self._binds_enabled:
            self.binds_switch.select()
        else:
            self.binds_switch.deselect()
        self.binds_switch.configure(text=f"Бинды: {'вкл' if self._binds_enabled else 'выкл'}")

        if persist:
            self.user_settings["binder_enabled"] = self._binds_enabled
            try:
                self.data_manager.save_settings(self.user_settings)
            except Exception:
                pass

        self._refresh_hotkeys(show_errors=False)

    def _toggle_binds(self):
        enabled = bool(self.binds_switch.get())
        if enabled and not self._hotkeys_manager.is_supported:
            messagebox.showwarning(
                "Бинды",
                "Глобальные бинды поддерживаются только на Windows.",
                parent=self
            )
            self._set_binds_switch_state(False)
            return

        self._set_binds_switch_state(enabled)
        status = "включены" if enabled else "выключены"
        if enabled:
            self._set_status(f"Бинды {status} (panic: {self._get_panic_hotkey()})")
            return
        self._set_status(f"Бинды {status}")

    def _get_binding_scope_items(self) -> list[dict]:
        scope_items = None
        get_scope_items = getattr(self, "_get_selected_category_items", None)
        if callable(get_scope_items):
            try:
                scope_items = get_scope_items()
            except Exception:
                scope_items = None

        if isinstance(scope_items, list):
            return [item for item in scope_items if isinstance(item, dict)]
        return [item for item in self._iter_all_items() if isinstance(item, dict)]

    @staticmethod
    def _normalize_item_hotkey(item: dict) -> str:
        raw_hotkey = str(item.get("hotkey", "")).strip()
        if not raw_hotkey:
            return ""
        try:
            return normalize_hotkey(raw_hotkey)
        except ValueError:
            return ""

    def _get_scope_hotkey_conflicts(self) -> dict[int, str]:
        groups: dict[str, list[dict]] = {}
        for item in self._get_binding_scope_items():
            if not bool(item.get("enabled", False)):
                continue
            normalized = self._normalize_item_hotkey(item)
            if not normalized:
                continue
            groups.setdefault(normalized, []).append(item)

        conflicts: dict[int, str] = {}
        for normalized, items in groups.items():
            if len(items) < 2:
                continue
            for item in items:
                conflicts[id(item)] = normalized
        return conflicts

    def _find_scope_hotkey_conflict(self, normalized_hotkey: str, current_item: dict) -> dict | None:
        current_item_id = str(current_item.get("item_id", "")).strip()
        for item in self._get_binding_scope_items():
            if item is current_item:
                continue
            if not bool(item.get("enabled", False)):
                continue
            item_id = str(item.get("item_id", "")).strip()
            if current_item_id and item_id and item_id == current_item_id:
                continue
            if self._normalize_item_hotkey(item) == normalized_hotkey:
                return item
        return None

    def _rebuild_hotkey_item_map(self):
        self._hotkey_item_map = {}
        self._hotkey_label_map = {}
        self._hotkey_label_map[self.PANIC_ITEM_ID] = "PANIC"

        for item in self._get_binding_scope_items():
            item_id = str(item.get("item_id", "")).strip()
            if not item_id:
                continue

            self._hotkey_item_map[item_id] = item
            title = str(item.get("title", "")).strip()
            self._hotkey_label_map[item_id] = title or item_id

    def _collect_bindings_for_runtime(self) -> dict[str, str]:
        bindings: dict[str, str] = {self.PANIC_ITEM_ID: self._get_panic_hotkey()}
        for item_id, item in self._hotkey_item_map.items():
            enabled = bool(item.get("enabled", False))
            hotkey = str(item.get("hotkey", "")).strip()
            send_mode = str(item.get("send_mode", "copy")).strip().lower()
            if enabled and hotkey and send_mode in {"copy", "paste", "paste_enter"}:
                bindings[item_id] = hotkey
        return bindings

    def _refresh_hotkeys(self, show_errors: bool = True, show_status: bool = False):
        self._rebuild_hotkey_item_map()
        if not self._binds_enabled:
            self._hotkeys_manager.stop()
            return

        bindings = self._collect_bindings_for_runtime()
        active_count, issues = self._hotkeys_manager.configure(bindings)
        formatted_issues: list[str] = []
        for issue in issues:
            item_id, sep, details = issue.partition(":")
            if not sep:
                formatted_issues.append(issue)
                continue
            label = self._hotkey_label_map.get(item_id.strip(), item_id.strip())
            formatted_issues.append(f"{label}:{details}")

        if show_errors and issues:
            messagebox.showwarning(
                "Бинды",
                "Некоторые бинды не активированы:\n\n" + "\n".join(formatted_issues[:8]),
                parent=self
            )

        if show_status:
            self._set_status(f"Активных биндов: {active_count}")

    def _copy_text_to_clipboard(self, text: str, status_text: str = "Скопировано ✅"):
        copy_to_clipboard(self, text)
        self._set_status(status_text)

    def _on_hotkey_trigger(self, item_id: str):
        self.after(0, lambda current_item_id=item_id: self._handle_hotkey_trigger(current_item_id))

    def _handle_hotkey_trigger(self, item_id: str):
        if getattr(self, "_hotkeys_temporarily_suspended", False):
            return

        if item_id == self.PANIC_ITEM_ID:
            self._trigger_panic()
            return

        item = self._hotkey_item_map.get(item_id)
        if not item:
            return

        text = self._render_item_text(item)
        if not text:
            return

        send_mode = str(item.get("send_mode", "copy")).strip().lower()
        if send_mode == "copy":
            self._copy_text_to_clipboard(text, status_text="Скопировано по бинду ✅")
            return

        delay_ms = self._parse_delay_ms(item.get("delay_ms", PASTE_ENTER_DEFAULT_DELAY_MS))
        should_press_enter = send_mode == "paste_enter"
        pasted = paste_text_to_active_window(
            self,
            text,
            press_enter=should_press_enter,
            enter_delay_seconds=delay_ms / 1000.0,
            restore_clipboard=False,
        )
        if pasted:
            if should_press_enter:
                self._set_status(f"Вставлено и отправлено ✅ ({delay_ms} мс)")
            else:
                self._set_status("Вставлено по бинду ✅")
            return

        # Fallback если авто-вставка недоступна.
        self._copy_text_to_clipboard(text, status_text="Скопировано (вставка недоступна)")

    def _trigger_panic(self):
        if not self._binds_enabled:
            return

        self._set_binds_switch_state(False)
        self._set_status("PANIC: все бинды отключены")

    def _update_bind_item_status(self):
        if not self.selected_item:
            self.bind_item_status.configure(text="Бинд: -")
            return

        conflicts = self._get_scope_hotkey_conflicts()
        conflict_hotkey = conflicts.get(id(self.selected_item))
        hotkey = str(self.selected_item.get("hotkey", "")).strip()
        enabled = bool(self.selected_item.get("enabled", False))
        send_mode = str(self.selected_item.get("send_mode", "copy")).strip().lower()
        if send_mode == "paste_enter":
            delay_ms = self._parse_delay_ms(self.selected_item.get("delay_ms", PASTE_ENTER_DEFAULT_DELAY_MS))
            mode_label = f"вставка+Enter ({delay_ms} мс)"
        elif send_mode == "paste":
            mode_label = "вставка"
        else:
            mode_label = "копия"
        if hotkey:
            suffix = " (вкл)" if enabled else " (выкл)"
            conflict_suffix = f", КОНФЛИКТ: {conflict_hotkey}" if conflict_hotkey else ""
            self.bind_item_status.configure(text=f"Бинд: {hotkey}{suffix}, {mode_label}{conflict_suffix}")
            return

        self.bind_item_status.configure(text="Бинд: -")

    def _refresh_items_view_after_bind_update(self):
        refresh_view = getattr(self, "_refresh_items_bind_highlight", None)
        if callable(refresh_view):
            refresh_view()

    def _configure_item_bind(self):
        if not self.selected_item:
            messagebox.showwarning("Бинды", "Сначала выберите фразу.", parent=self)
            return

        item = self.selected_item
        result: dict[str, dict | None] = {"value": None}

        dialog = ctk.CTkToplevel(self)
        dialog.title("Менеджер бинда")
        dialog.resizable(False, False)
        dialog.transient(self)

        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            frame,
            text="Настройка: хоткей, режим отправки, задержка и состояние.",
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        hotkey_row = ctk.CTkFrame(frame, fg_color="transparent")
        hotkey_row.pack(fill="x", pady=(0, 8))
        hotkey_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hotkey_row, text="Хоткей:").grid(row=0, column=0, padx=(0, 8), sticky="w")
        hotkey_var = tk.StringVar(value=str(item.get("hotkey", "")).strip())
        hotkey_entry = ctk.CTkEntry(hotkey_row, textvariable=hotkey_var)
        hotkey_entry.grid(row=0, column=1, sticky="ew")

        capture_btn = ctk.CTkButton(hotkey_row, text="Захватить", width=92)
        capture_btn.grid(row=0, column=2, padx=(6, 0), sticky="ew")

        clear_btn = ctk.CTkButton(hotkey_row, text="Очистить", width=92, command=lambda: hotkey_var.set(""))
        clear_btn.grid(row=0, column=3, padx=(6, 0), sticky="ew")

        enabled_var = tk.BooleanVar(value=bool(item.get("enabled", False)))
        enabled_switch = ctk.CTkSwitch(frame, text="Включить бинд", variable=enabled_var, onvalue=True, offvalue=False)
        enabled_switch.pack(anchor="w", pady=(0, 8))

        mode_row = ctk.CTkFrame(frame, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, 8))
        mode_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(mode_row, text="Режим:").grid(row=0, column=0, padx=(0, 8), sticky="w")
        mode_var = tk.StringVar(value=str(item.get("send_mode", "copy")).strip().lower() or "copy")
        if mode_var.get() not in {"copy", "paste", "paste_enter"}:
            mode_var.set("copy")
        mode_selector = ctk.CTkSegmentedButton(mode_row, values=["copy", "paste", "paste_enter"], variable=mode_var)
        mode_selector.grid(row=0, column=1, sticky="ew")

        delay_row = ctk.CTkFrame(frame, fg_color="transparent")
        delay_row.pack(fill="x", pady=(0, 10))
        delay_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(delay_row, text="Задержка Enter (мс):").grid(row=0, column=0, padx=(0, 8), sticky="w")
        delay_var = tk.StringVar(value=str(self._parse_delay_ms(item.get("delay_ms", PASTE_ENTER_DEFAULT_DELAY_MS))))
        delay_entry = ctk.CTkEntry(delay_row, textvariable=delay_var)
        delay_entry.grid(row=0, column=1, sticky="ew")

        info_var = tk.StringVar(value="")
        ctk.CTkLabel(frame, textvariable=info_var, justify="left").pack(anchor="w", pady=(0, 6))

        def refresh_delay_state():
            if mode_var.get() == "paste_enter":
                delay_entry.configure(state="normal")
            else:
                delay_entry.configure(state="disabled")

        def capture_hotkey():
            try:
                dialog.grab_release()
            except Exception:
                pass

            captured = self._capture_hotkey(hotkey_var.get().strip())

            dialog.grab_set()
            dialog.focus_force()
            if captured is None:
                return
            hotkey_var.set(captured.strip())
            if hotkey_var.get():
                enabled_var.set(True)

        capture_btn.configure(command=capture_hotkey)
        mode_selector.configure(command=lambda _value: refresh_delay_state())
        refresh_delay_state()

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x")
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        def close_with(value: dict | None):
            result["value"] = value
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        def save_bind():
            raw_hotkey = hotkey_var.get().strip()
            normalized_hotkey = ""
            if raw_hotkey:
                try:
                    normalized_hotkey = normalize_hotkey(raw_hotkey)
                except ValueError as error:
                    messagebox.showwarning("Бинды", str(error), parent=dialog)
                    return

            enabled = bool(enabled_var.get())
            if enabled and not normalized_hotkey:
                messagebox.showwarning("Бинды", "Для включенного бинда нужно указать хоткей.", parent=dialog)
                return

            selected_mode = mode_var.get().strip().lower()
            if selected_mode not in {"copy", "paste", "paste_enter"}:
                selected_mode = "copy"

            selected_delay = self._parse_delay_ms(delay_var.get().strip() or PASTE_ENTER_DEFAULT_DELAY_MS)

            if enabled and normalized_hotkey:
                conflict_item = self._find_scope_hotkey_conflict(normalized_hotkey, current_item=item)
                if conflict_item is not None:
                    conflict_title = str(conflict_item.get("title", "Без названия")).strip() or "Без названия"
                    messagebox.showwarning(
                        "Конфликт хоткеев",
                        "Этот хоткей уже используется в текущем отделе.\n"
                        f"Конфликтующая фраза: {conflict_title}\n\n"
                        "Выберите другой хоткей или отключите один из конфликтующих бинов.",
                        parent=dialog,
                    )
                    return

            info_var.set("")
            close_with({
                "hotkey": normalized_hotkey,
                "enabled": enabled,
                "send_mode": selected_mode,
                "delay_ms": selected_delay,
            })

        ctk.CTkButton(actions, text="Сохранить", command=save_bind).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(actions, text="Отмена", command=lambda: close_with(None)).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        dialog.focus_force()
        dialog.grab_set()
        self._center_popup(dialog, fallback_width=560, fallback_height=280)
        hotkey_entry.focus_set()
        dialog.wait_window()

        if result["value"] is None:
            return

        bind_config = result["value"]
        item["hotkey"] = str(bind_config.get("hotkey", "")).strip()
        item["enabled"] = bool(bind_config.get("enabled", False))
        item["send_mode"] = str(bind_config.get("send_mode", "copy")).strip().lower()
        item["delay_ms"] = self._parse_delay_ms(bind_config.get("delay_ms", PASTE_ENTER_DEFAULT_DELAY_MS))
        if not item.get("item_id"):
            item["item_id"] = self.data_manager.generate_item_id()

        saved = self._persist_profiles(refresh_hotkeys=False)
        self._refresh_items_view_after_bind_update()
        if saved and self._binds_enabled:
            self._refresh_hotkeys(show_errors=True, show_status=True)
        self._update_bind_item_status()
        if saved:
            if item["enabled"] and item["hotkey"]:
                self._set_status(f"Бинд обновлен: {item['hotkey']}")
            else:
                self._set_status("Бинд отключен")
