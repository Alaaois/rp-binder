# RP Binder

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Windows Hotkeys](https://img.shields.io/badge/Global%20hotkeys-Windows%20only-0078D6)](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-registerhotkey)
[![Status](https://img.shields.io/badge/status-active-success)](#)
[![Last Commit](https://img.shields.io/github/last-commit/Alaaois/rp-binder)](https://github.com/Alaaois/rp-binder)

Desktop-утилита для RP-шаблонов: профили, отделы, фразы, бинды и импорт/экспорт JSON.

Важно: проект поддерживает user-triggered биндинг и эмуляцию клавиатурного ввода для чат-сценариев.
Ограничения остаются: без инжекта в память процессов, без packet-manipulation и без anti-cheat bypass.
Поддерживаемая платформа: только Windows.

![RP Binder Preview](assets/app_preview.png)

## Возможности

- Профили служб: например `Полиция`, `РЖД`, `Медики`.
- Отделы внутри профиля и фразы внутри отдела.
- Встроенный редактор текста фразы с нумерацией строк.
- Биндер с режимами `copy`, `paste`, `paste_enter`, `chat_send`.
- Настройка бинда в одном окне: хоткей, режим, задержка, вкл/выкл.
- Поддержка numpad-хоткеев (`Num0..Num9`, `NumPlus`, `NumMinus`, `NumMultiply`, `NumDivide`, `NumDecimal`).
- Проверка конфликтов хоткеев до сохранения + подсветка конфликтов в списке фраз.
- Panic hotkey (`End`) и временный panic при записи нового хоткея.
- Импорт профилей: `заменить` или `объединить (merge без дублей фраз)`.
- Экспорт выбранного профиля в JSON.
- Импорт/экспорт выбранного отдела (`Imp` / `Exp`).
- Проверка обновлений в фоне (без блокировки интерфейса).

## Быстрый старт

### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Сборка

Рекомендуемый вариант (через `main.spec`):

```bash
pyinstaller --noconfirm --clean main.spec
```

Быстрый вариант без `spec`:

```bash
pyinstaller --noconfirm --onefile --windowed main.py
```

## Конфигурация через `.env` (dev)

Переменные:

- `RPB_APP_VERSION` — версия приложения в заголовке.
- `RPB_UPDATE_INFO_URL` — URL до `version.json` для проверки обновлений.

Важно:

- `.env` используется только в dev-запуске (`python main.py`).
- В собранном `exe` используются релизные значения из `app/updater.py`:
  - `RELEASE_APP_VERSION`
  - `RELEASE_UPDATE_INFO_URL`

Пример:

```env
RPB_APP_VERSION=0.1.1
RPB_UPDATE_INFO_URL=https://your-domain/version.json
```

## Как использовать

1. Выберите или создайте профиль.
2. Добавьте отдел.
3. Добавьте фразы/команды.
4. Откройте `Бинд` у нужной фразы и настройте хоткей/режим/задержку.
5. Включите общий переключатель `Бинды`.

## Форматы JSON

### Профили (`profiles`)

```json
{
  "version": "1.1",
  "profiles": [
    {
      "profile_name": "Полиция",
      "categories": [
        {
          "name": "ДПС",
          "items": [
            {
              "title": "Остановка ТС",
              "text": "/m Водитель, прижмитесь к обочине.",
              "item_id": "auto-generated-id",
              "hotkey": "Ctrl+1",
              "enabled": true,
              "send_mode": "paste_enter",
              "delay_ms": 120
            }
          ]
        }
      ]
    }
  ]
}
```

Поля `items[]`:

- `title` (string)
- `text` (string)
- `item_id` (string, создается автоматически при необходимости)
- `hotkey` (string)
- `enabled` (bool)
- `send_mode` (`copy` | `paste` | `paste_enter` | `chat_send`)
- `delay_ms` (0..5000)
- `chat_open_hotkey` (string, по умолчанию `T`)
- `chat_open_delay_ms` (0..5000)
- `chat_send_each_line` (bool, отправлять каждую строку отдельным сообщением)

### Пакет отдела (`category-pack-v1`)

```json
{
  "version": "1.1",
  "format": "category-pack-v1",
  "profile_name": "Полиция",
  "category": {
    "name": "ДПС",
    "items": [
      {
        "title": "Остановка ТС",
        "text": "/m Водитель, прижмитесь к обочине."
      }
    ]
  }
}
```

Импорт отдела:

- если отдела с таким именем нет: отдел добавляется;
- если есть: можно `заменить` целиком или `объединить` без дублей (`title + text`).

## Логика биндера

- Глобальные хоткеи: только Windows (`RegisterHotKey`).
- Область действия: активен только выбранный отдел (плюс panic hotkey).
- `copy`: копирование в буфер.
- `paste`: вставка в активное окно через `Ctrl+V`.
- `paste_enter`: вставка + `Enter` с задержкой `delay_ms`.
- `chat_send`: открыть чат (`chat_open_hotkey`) -> подождать `chat_open_delay_ms` -> вставка + `Enter`.
- Если `chat_send_each_line=true`, каждая непустая строка отправляется отдельным сообщением.

## Безопасность и границы проекта

Проект сознательно не делает:

- инжект/хуки в процесс игры;
- чтение памяти игры;
- пакетные/сетевые вмешательства;
- обход античита.

## Тесты

```bash
python -m unittest discover -s tests -v
```

## Структура проекта

- `main.py` — точка входа.
- `app/ui.py` — основной UI.
- `app/ui_mixins/*` — логика UI по модулям.
- `app/data_manager.py` — загрузка/валидация/сохранение JSON.
- `app/binder.py` — глобальные хоткеи.
- `app/updater.py` — проверка обновлений.
- `data/default_profile.json` — встроенный профиль.

## Roadmap

- [ ] Избранные фразы.
- [ ] История последних срабатываний.
- [ ] Массовые операции по отделу (вкл/выкл все, очистка хоткеев).
- [ ] Поиск по хоткею.
- [ ] Резервные копии профилей.

## Contribution

PR приветствуются. Перед PR:

1. Прогоните `python -m unittest discover -s tests -v`.
2. Проверьте ручной сценарий: загрузка профиля, выбор отдела, бинды, импорт/экспорт.
3. Не добавляйте функционал, связанный с инжектом/памятью/обходом античита.
