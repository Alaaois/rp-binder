import queue
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

import customtkinter as ctk

from app.binder import GlobalHotkeyBinder
from app.constants import (
    APP_NAME,
    CENTER_COLUMN_MIN_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    LEFT_COLUMN_MIN_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    PANIC_HOTKEY_DEFAULT,
    RIGHT_COLUMN_MIN_WIDTH,
)
from app.data_manager import DataManager
from app.ui_mixins.binder_mixin import UIBinderMixin
from app.ui_mixins.editor_mixin import UIEditorMixin
from app.ui_mixins.profile_mixin import UIProfileMixin
from app.updater import APP_VERSION, check_for_updates


def _pick_theme_color(value: str | list[str] | tuple[str, ...]) -> str:
    """Возвращает цвет под текущий режим темы CustomTkinter."""
    if isinstance(value, (list, tuple)):
        if not value:
            return "#1f1f1f"
        mode = ctk.get_appearance_mode().lower()
        if mode == "dark" and len(value) > 1:
            return value[1]
        return value[0]
    return value


class RPAssistantApp(UIProfileMixin, UIBinderMixin, UIEditorMixin, ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        self.data_manager = DataManager()
        self.data = None
        self.profile = None
        self.profiles_map = {}
        self.user_settings = {
            "nick": "",
            "position": "",
            "binder_enabled": False,
            "panic_hotkey": PANIC_HOTKEY_DEFAULT,
        }

        self.inline_edit_mode = False
        self.inline_edit_item = None
        self._preview_poll_after_id = None

        self._updates_queue: queue.Queue[dict | None] = queue.Queue()
        self._update_thread: threading.Thread | None = None

        self._hotkey_item_map: dict[str, dict] = {}
        self._hotkey_label_map: dict[str, str] = {}
        self._binds_enabled = False
        self._hotkeys_temporarily_suspended = False
        self._hotkeys_manager = GlobalHotkeyBinder(on_trigger=self._on_hotkey_trigger)

        self.category_map = {}
        self.filtered_items = []

        self._build_ui()
        self._center_window()

        if not self._ensure_registration():
            self.after(10, self.destroy)
            return

        self._binds_enabled = bool(self.user_settings.get("binder_enabled", False))
        self._load_startup_profiles()
        self._set_binds_switch_state(self._binds_enabled, persist=False)
        self._start_background_update_check()

    def _start_background_update_check(self):
        self._update_thread = threading.Thread(target=self._check_updates_worker, daemon=True)
        self._update_thread.start()
        self.after(200, self._poll_update_check_result)

    def destroy(self):
        try:
            self._hotkeys_manager.stop()
        except Exception:
            pass
        super().destroy()

    def _check_updates_worker(self):
        update_info = check_for_updates()
        self._updates_queue.put(update_info)

    def _poll_update_check_result(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            update_info = self._updates_queue.get_nowait()
        except queue.Empty:
            if self._update_thread and self._update_thread.is_alive():
                self.after(200, self._poll_update_check_result)
            return

        if not update_info:
            return

        version = update_info.get("version", "?")
        url = update_info.get("url")
        answer = messagebox.askyesno(
            "Доступно обновление",
            f"Найдена новая версия: {version}\n\nОткрыть страницу обновления?",
            parent=self,
        )
        if answer and url:
            webbrowser.open(url)

    def _center_window(self):
        self._center_popup(self, fallback_width=DEFAULT_WINDOW_WIDTH, fallback_height=DEFAULT_WINDOW_HEIGHT)

    @staticmethod
    def _center_popup(window: tk.Misc, fallback_width: int = 420, fallback_height: int = 220):
        window.update_idletasks()

        width = window.winfo_width()
        height = window.winfo_height()
        req_width = window.winfo_reqwidth()
        req_height = window.winfo_reqheight()

        if width <= 1:
            width = req_width
        if height <= 1:
            height = req_height

        width = max(width, req_width, fallback_width)
        height = max(height, req_height, fallback_height)

        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2, 0)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _style_native_listbox(self, listbox: tk.Listbox):
        theme = ctk.ThemeManager.theme
        bg = _pick_theme_color(theme["CTkFrame"]["fg_color"])
        fg = _pick_theme_color(theme["CTkLabel"]["text_color"])
        select_bg = _pick_theme_color(theme["CTkButton"]["hover_color"])
        select_fg = _pick_theme_color(theme["CTkButton"]["text_color"])

        listbox.configure(
            bg=bg,
            fg=fg,
            selectbackground=select_bg,
            selectforeground=select_fg,
            highlightbackground=bg,
            highlightcolor=bg,
            borderwidth=0,
            relief="flat",
            activestyle="none",
            font=("Segoe UI", 11),
        )

    def _style_line_numbers(self):
        theme = ctk.ThemeManager.theme
        bg = _pick_theme_color(theme["CTkFrame"]["fg_color"])
        fg = _pick_theme_color(theme["CTkLabel"]["text_color"])

        self.preview_line_numbers.configure(
            bg=bg,
            fg=fg,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=6,
            pady=8,
            font=("Consolas", 11),
            cursor="arrow",
        )

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1, minsize=LEFT_COLUMN_MIN_WIDTH)
        self.grid_columnconfigure(1, weight=2, minsize=CENTER_COLUMN_MIN_WIDTH)
        self.grid_columnconfigure(2, weight=3, minsize=RIGHT_COLUMN_MIN_WIDTH)
        self.grid_rowconfigure(1, weight=1)

        topbar = ctk.CTkFrame(self)
        topbar.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=8, pady=(8, 4))
        topbar.grid_columnconfigure(0, weight=1)

        topbar_main = ctk.CTkFrame(topbar, fg_color="transparent")
        topbar_main.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 2))
        topbar_main.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(topbar_main, text="Профиль:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=(10, 6), pady=(10, 6), sticky="w"
        )

        self.profile_selector = ctk.CTkComboBox(
            topbar_main,
            values=["-"],
            command=self._on_profile_changed,
            state="readonly",
            width=230,
        )
        self.profile_selector.grid(row=0, column=1, padx=(0, 10), pady=(10, 6), sticky="w")
        self.profile_selector.set("-")

        self.profile_add_btn = ctk.CTkButton(topbar_main, text="+", width=34, command=self._add_profile)
        self.profile_add_btn.grid(row=0, column=2, padx=(0, 4), pady=(10, 6))

        self.profile_rename_btn = ctk.CTkButton(topbar_main, text="Переим.", width=76, command=self._rename_profile)
        self.profile_rename_btn.grid(row=0, column=3, padx=(0, 4), pady=(10, 6))

        self.profile_delete_btn = ctk.CTkButton(topbar_main, text="Удал.", width=64, command=self._delete_profile)
        self.profile_delete_btn.grid(row=0, column=4, padx=(0, 10), pady=(10, 6))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = ctk.CTkEntry(
            topbar_main,
            textvariable=self.search_var,
            placeholder_text="Поиск по названию или тексту...",
        )
        self.search_entry.grid(row=0, column=5, padx=10, pady=(10, 6), sticky="ew")

        self.import_btn = ctk.CTkButton(topbar_main, text="Импорт JSON", command=self._import_json)
        self.import_btn.grid(row=0, column=6, padx=10, pady=(10, 6))

        self.export_btn = ctk.CTkButton(topbar_main, text="Экспорт профиля", command=self._export_profile)
        self.export_btn.grid(row=0, column=7, padx=(0, 10), pady=(10, 6))

        topbar_meta = ctk.CTkFrame(topbar, fg_color="transparent")
        topbar_meta.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        topbar_meta.grid_columnconfigure(0, weight=1)

        self.user_label = ctk.CTkLabel(topbar_meta, text="Пользователь: -")
        self.user_label.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="w")

        self.edit_user_btn = ctk.CTkButton(topbar_meta, text="Ник / должность", command=self._edit_user_settings)
        self.edit_user_btn.grid(row=0, column=1, padx=(0, 10), pady=0, sticky="e")

        self.binds_switch = ctk.CTkSwitch(topbar_meta, text="Бинды: выкл", command=self._toggle_binds)
        self.binds_switch.grid(row=0, column=2, padx=(0, 0), pady=0, sticky="e")

        left = ctk.CTkFrame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=4)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        cat_header = ctk.CTkFrame(left, fg_color="transparent")
        cat_header.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        cat_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(cat_header, text="Отделы", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w")

        cat_actions = ctk.CTkFrame(cat_header, fg_color="transparent")
        cat_actions.grid(row=1, column=0, pady=(6, 0), sticky="w")

        self.category_add_btn = ctk.CTkButton(cat_actions, text="+", width=30, command=self._add_category)
        self.category_add_btn.grid(row=0, column=0, padx=(0, 4))

        self.category_rename_btn = ctk.CTkButton(cat_actions, text="Ред.", width=42, command=self._rename_category)
        self.category_rename_btn.grid(row=0, column=1, padx=(0, 4))

        self.category_delete_btn = ctk.CTkButton(cat_actions, text="Del", width=38, command=self._delete_category)
        self.category_delete_btn.grid(row=0, column=2, padx=(0, 0))

        self.category_import_btn = ctk.CTkButton(cat_actions, text="Imp", width=42, command=self._import_category_json)
        self.category_import_btn.grid(row=0, column=3, padx=(4, 0))

        self.category_export_btn = ctk.CTkButton(cat_actions, text="Exp", width=42, command=self._export_category_json)
        self.category_export_btn.grid(row=0, column=4, padx=(4, 0))

        self.category_listbox = tk.Listbox(left, exportselection=False)
        self._style_native_listbox(self.category_listbox)
        self.category_listbox.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.category_listbox.bind("<<ListboxSelect>>", self._on_category_selected)

        center = ctk.CTkFrame(self)
        center.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        center.grid_rowconfigure(2, weight=1)
        center.grid_columnconfigure(0, weight=1)

        items_header = ctk.CTkFrame(center, fg_color="transparent")
        items_header.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        items_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(items_header, text="Фразы / Скрипты", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )

        item_actions = ctk.CTkFrame(items_header, fg_color="transparent")
        item_actions.grid(row=1, column=0, pady=(6, 0), sticky="w")

        self.item_add_btn = ctk.CTkButton(item_actions, text="+", width=30, command=self._add_item)
        self.item_add_btn.grid(row=0, column=0, padx=(0, 4))

        self.item_edit_btn = ctk.CTkButton(item_actions, text="Ред.", width=42, command=self._edit_item)
        self.item_edit_btn.grid(row=0, column=1, padx=(0, 4))

        self.item_delete_btn = ctk.CTkButton(item_actions, text="Del", width=38, command=self._delete_item)
        self.item_delete_btn.grid(row=0, column=2, padx=(0, 0))

        self.items_listbox = tk.Listbox(center, exportselection=False)
        self._style_native_listbox(self.items_listbox)
        self.items_listbox.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.items_listbox.bind("<<ListboxSelect>>", self._on_item_selected)

        right = ctk.CTkFrame(self)
        right.grid(row=1, column=2, sticky="nsew", padx=(4, 8), pady=4)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Предпросмотр", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w"
        )

        self.preview_line_numbers = tk.Text(right, width=5, wrap="none", takefocus=0)
        self._style_line_numbers()
        self.preview_line_numbers.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="ns")
        self.preview_line_numbers.configure(state="disabled")

        self.preview_text = ctk.CTkTextbox(right, wrap="word")
        self.preview_text.grid(row=1, column=1, padx=(6, 10), pady=(0, 10), sticky="nsew")
        self.preview_text.insert("1.0", "Выбери фразу слева")
        self.preview_text.configure(state="disabled")

        self.preview_text._textbox.bind("<KeyRelease>", lambda _event: self._refresh_line_numbers())
        self.preview_text._textbox.bind("<ButtonRelease-1>", lambda _event: self._sync_line_numbers_yview())
        self.preview_text._textbox.bind("<MouseWheel>", lambda _event: self._defer_sync_line_numbers())
        self.preview_text._textbox.bind("<Control-c>", self._copy_preview_selection, add="+")
        self.preview_text._textbox.bind("<Control-C>", self._copy_preview_selection, add="+")
        self.preview_text._textbox.bind("<Control-Insert>", self._copy_preview_selection, add="+")
        self.preview_text._textbox.bind("<Control-a>", self._select_all_preview_text, add="+")
        self.preview_text._textbox.bind("<Control-A>", self._select_all_preview_text, add="+")

        self.preview_line_numbers.bind("<MouseWheel>", self._on_line_numbers_mousewheel)
        self.preview_line_numbers.bind("<Button-1>", lambda _event: "break")

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        bind_row = ctk.CTkFrame(btn_row, fg_color="transparent")
        bind_row.grid(row=0, column=0, sticky="ew")
        bind_row.grid_columnconfigure(0, weight=1)
        bind_row.grid_columnconfigure(1, weight=1)

        self.copy_btn = ctk.CTkButton(bind_row, text="Скопировать", width=110, command=self._copy_selected_text)
        self.copy_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.bind_item_btn = ctk.CTkButton(bind_row, text="Бинд", width=110, command=self._configure_item_bind)
        self.bind_item_btn.grid(row=0, column=1, padx=(0, 0), sticky="ew")

        edit_row = ctk.CTkFrame(btn_row, fg_color="transparent")
        edit_row.grid(row=1, column=0, pady=(6, 0), sticky="ew")
        edit_row.grid_columnconfigure(0, weight=1)
        edit_row.grid_columnconfigure(1, weight=1)
        edit_row.grid_columnconfigure(2, weight=1)

        self.inline_edit_btn = ctk.CTkButton(edit_row, text="Редактировать", width=110, command=self._start_inline_edit)
        self.inline_edit_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.inline_save_btn = ctk.CTkButton(edit_row, text="Сохранить", width=110, command=self._save_inline_edit, state="disabled")
        self.inline_save_btn.grid(row=0, column=1, padx=(0, 5), sticky="ew")

        self.inline_cancel_btn = ctk.CTkButton(edit_row, text="Отмена", width=110, command=self._cancel_inline_edit, state="disabled")
        self.inline_cancel_btn.grid(row=0, column=2, padx=(0, 0), sticky="ew")

        status_row = ctk.CTkFrame(btn_row, fg_color="transparent")
        status_row.grid(row=2, column=0, pady=(6, 0), sticky="ew")
        status_row.grid_columnconfigure(1, weight=1)

        self.bind_item_status = ctk.CTkLabel(status_row, text="Бинд: -")
        self.bind_item_status.grid(row=0, column=0, padx=(0, 12), sticky="w")

        self.copy_status = ctk.CTkLabel(status_row, text="")
        self.copy_status.grid(row=0, column=1, sticky="w")

        self._disabled_while_editing = [
            (self.copy_btn, "normal"),
            (self.bind_item_btn, "normal"),
            (self.binds_switch, "normal"),
            (self.profile_selector, "readonly"),
            (self.search_entry, "normal"),
            (self.import_btn, "normal"),
            (self.export_btn, "normal"),
            (self.edit_user_btn, "normal"),
            (self.profile_add_btn, "normal"),
            (self.profile_rename_btn, "normal"),
            (self.profile_delete_btn, "normal"),
            (self.category_add_btn, "normal"),
            (self.category_rename_btn, "normal"),
            (self.category_delete_btn, "normal"),
            (self.category_import_btn, "normal"),
            (self.category_export_btn, "normal"),
            (self.item_add_btn, "normal"),
            (self.item_edit_btn, "normal"),
            (self.item_delete_btn, "normal"),
            (self.category_listbox, "normal"),
            (self.items_listbox, "normal"),
            (self.inline_edit_btn, "normal"),
        ]

        self._enabled_while_editing = [
            (self.inline_save_btn, "normal"),
            (self.inline_cancel_btn, "normal"),
        ]

        self.selected_item = None
        self._refresh_line_numbers()
        self._schedule_preview_poll()

    def _schedule_preview_poll(self):
        if self._preview_poll_after_id is not None:
            return

        def _poll():
            self._preview_poll_after_id = None
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return

            self._refresh_line_numbers()
            self._schedule_preview_poll()

        self._preview_poll_after_id = self.after(150, _poll)

    def _defer_sync_line_numbers(self):
        self.after(10, self._sync_line_numbers_yview)
        return None

    def _on_line_numbers_mousewheel(self, event):
        self.preview_text._textbox.yview_scroll(int(-event.delta / 120), "units")
        self._sync_line_numbers_yview()
        return "break"

    def _sync_line_numbers_yview(self):
        first, _last = self.preview_text._textbox.yview()
        self.preview_line_numbers.yview_moveto(first)

    def _refresh_line_numbers(self):
        line_count = int(self.preview_text._textbox.index("end-1c").split(".")[0])
        line_count = max(line_count, 1)
        numbers = "\n".join(str(index) for index in range(1, line_count + 1))

        self.preview_line_numbers.configure(state="normal")
        self.preview_line_numbers.delete("1.0", tk.END)
        self.preview_line_numbers.insert("1.0", numbers)
        self.preview_line_numbers.configure(state="disabled")
        self._sync_line_numbers_yview()
