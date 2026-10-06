"""Простая i18n: ru / en, выбор через cookie ntdc_lang или ?lang=."""

from __future__ import annotations

from typing import Any

SUPPORTED = ("ru", "en")
DEFAULT_LANG = "ru"
COOKIE_NAME = "ntdc_lang"

# short_name / full_name per language
BRAND = {
    "ru": {
        "short": "NTDC",
        "full": "Конфигуратор устройств сетевой телефонии",
    },
    "en": {
        "short": "NTDC",
        "full": "Network Telephony Device Configurator",
    },
}

# key -> {ru, en}
MESSAGES: dict[str, dict[str, str]] = {
    "nav.dashboard": {"ru": "Панель", "en": "Dashboard"},
    "nav.devices": {"ru": "Устройства", "en": "Devices"},
    "nav.device_list": {"ru": "Список устройств", "en": "Device list"},
    "nav.accounts": {"ru": "Аккаунты", "en": "Accounts"},
    "nav.sip_accounts": {"ru": "SIP-аккаунты", "en": "SIP accounts"},
    "nav.config": {"ru": "Конфигурация", "en": "Configuration"},
    "nav.global_config": {"ru": "Глобальные настройки", "en": "Global Config"},
    "nav.models": {"ru": "Модели", "en": "Models"},
    "nav.system": {"ru": "Система", "en": "System"},
    "nav.users": {"ru": "Пользователи", "en": "Users"},
    "nav.audit": {"ru": "Журнал аудита", "en": "Audit log"},
    "nav.logout": {"ru": "Выйти", "en": "Log out"},
    "nav.login": {"ru": "Войти", "en": "Sign in"},
    "login.title": {"ru": "Вход", "en": "Sign in"},
    "login.username": {"ru": "Имя пользователя", "en": "Username"},
    "login.password": {"ru": "Пароль", "en": "Password"},
    "login.submit": {"ru": "Войти", "en": "Sign in"},
    "login.error": {"ru": "Неверный логин или пароль", "en": "Invalid username or password"},
    "login.locked": {"ru": "Слишком много попыток. Попробуйте позже.", "en": "Too many attempts. Try again later."},
    "common.search": {"ru": "Поиск", "en": "Search"},
    "common.add": {"ru": "Добавить", "en": "Add"},
    "common.save": {"ru": "Сохранить", "en": "Save"},
    "common.cancel": {"ru": "Отмена", "en": "Cancel"},
    "common.delete": {"ru": "Удалить", "en": "Delete"},
    "common.edit": {"ru": "Редактировать", "en": "Edit"},
    "common.actions": {"ru": "Действия", "en": "Actions"},
    "common.reset": {"ru": "Сброс", "en": "Reset"},
    "common.find": {"ru": "Найти", "en": "Search"},
    "common.total": {"ru": "Всего", "en": "Total"},
    "common.online": {"ru": "Online", "en": "Online"},
    "common.offline": {"ru": "Offline", "en": "Offline"},
    "common.all_statuses": {"ru": "Все статусы", "en": "All statuses"},
    "phones.title": {"ru": "Список устройств", "en": "Device list"},
    "phones.search_ph": {"ru": "Поиск: MAC, модель, IP…", "en": "Search: MAC, model, IP…"},
    "phones.empty": {"ru": "Нет устройств. Добавьте вручную или включите AUTO_ENROLL.", "en": "No devices. Add manually or enable AUTO_ENROLL."},
    "phones.none_found": {"ru": "Ничего не найдено по запросу", "en": "Nothing found for"},
    "accounts.title": {"ru": "SIP-аккаунты", "en": "SIP accounts"},
    "accounts.search_ph": {"ru": "Поиск: имя, username, сервер…", "en": "Search: name, username, server…"},
    "accounts.empty": {"ru": "Нет аккаунтов. Нажмите «Добавить».", "en": "No accounts. Click Add."},
    "accounts.import_csv": {"ru": "Импорт CSV", "en": "Import CSV"},
    "accounts.import_csv_title": {"ru": "Импорт из FreePBX (CSV)", "en": "Import from FreePBX (CSV)"},
    "accounts.import_csv_help": {
        "ru": "Выгрузка Extensions из FreePBX. Поля: extension→username, secret→password, name, description. При совпадении username — обновление.",
        "en": "FreePBX Extensions export. Fields: extension→username, secret→password, name, description. Matching username is updated.",
    },
    "accounts.import_csv_btn": {"ru": "Импортировать", "en": "Import"},
    "accounts.sip_server": {"ru": "SIP Server", "en": "SIP Server"},
    "accounts.sip_port": {"ru": "SIP Port", "en": "SIP Port"},
    "users.title": {"ru": "Пользователи сервиса", "en": "Service users"},
    "lang.ru": {"ru": "Русский", "en": "Russian"},
    "lang.en": {"ru": "English", "en": "English"},
    "pagination.shown": {"ru": "Показано", "en": "Showing"},
    "pagination.of": {"ru": "из", "en": "of"},
    "pagination.per_page": {"ru": "На стр.", "en": "Per page"},
    "settings.title": {"ru": "Глобальные настройки", "en": "Global Configuration"},
    "settings.custom": {"ru": "Дополнительные параметры", "en": "Custom parameters"},
    "settings.auto_enroll": {"ru": "Автодобавление устройств", "en": "Auto-Enroll"},
    "settings.auto_enroll_30": {"ru": "Включить на 30 минут", "en": "Enable for 30 minutes"},
    "settings.auto_enroll_60": {"ru": "Включить на 60 минут", "en": "Enable for 60 minutes"},
    "settings.auto_enroll_off": {"ru": "Выключить", "en": "Disable Auto-Enroll"},
    "settings.auto_enroll_on": {"ru": "Автодобавление ВКЛЮЧЕНО", "en": "Auto-Enroll is ENABLED"},
    "settings.auto_enroll_disabled": {"ru": "Автодобавление ВЫКЛЮЧЕНО", "en": "Auto-Enroll is DISABLED"},
    "settings.until": {"ru": "До", "en": "Until"},
    "settings.remaining": {"ru": "Осталось (мин)", "en": "Remaining (min)"},
    "settings.import_title": {"ru": "Импорт конфигураций", "en": "Import configurations"},
    "settings.import_help": {
        "ru": "Загрузите файлы, экспортированные скриптом yealink_bulk_export.py. Сервис извлечёт MAC из имени файла, создаст/найдёт SIP-аккаунты и DSS, уберёт совпадающее с Global Config и моделью.",
        "en": "Upload files exported by yealink_bulk_export.py. The service extracts MAC from the filename, creates/finds SIP accounts and DSS keys, and subtracts keys matching Global Config and model defaults.",
    },
    "settings.import_model_auto": {"ru": "— Авто (из имени файла / содержимого cfg) —", "en": "— Auto (from filename / cfg content) —"},
    "settings.import_promote": {
        "ru": "Перенести параметры, одинаковые во всех файлах, в глобальные настройки",
        "en": "Promote keys common to all files into Global Config",
    },
    "settings.import_btn": {"ru": "Импортировать", "en": "Import"},
    "settings.enabled": {"ru": "Вкл", "en": "Enabled"},
    "settings.disabled": {"ru": "Выкл", "en": "Disabled"},
    "common.remove": {"ru": "Удалить", "en": "Remove"},
    "dash.title": {"ru": "Панель", "en": "Dashboard"},
    "dash.total_devices": {"ru": "Всего устройств", "en": "Total devices"},
    "dash.online": {"ru": "Online", "en": "Online"},
    "dash.dnd": {"ru": "DND", "en": "DND"},
    "dash.offline": {"ru": "Offline / Unreg", "en": "Offline / Unreg"},
    "dash.quick": {"ru": "Быстрые действия", "en": "Quick actions"},
    "dash.devices": {"ru": "Устройства", "en": "Devices"},
    "dash.add_device": {"ru": "Добавить устройство", "en": "Add device"},
    "dash.accounts": {"ru": "Аккаунты", "en": "Accounts"},
    "dash.global_config": {"ru": "Глобальные настройки", "en": "Global Config"},


}



def normalize_lang(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANG
    lang = lang.strip().lower()[:2]
    return lang if lang in SUPPORTED else DEFAULT_LANG


def translate(key: str, lang: str | None = None, **kwargs: Any) -> str:
    lang = normalize_lang(lang)
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def brand_short(lang: str | None = None) -> str:
    return BRAND[normalize_lang(lang)]["short"]


def brand_full(lang: str | None = None) -> str:
    return BRAND[normalize_lang(lang)]["full"]


class Translator:
    """Объект для шаблонов: {{ t('nav.users') }}, {{ t.short }}, {{ t.full }}."""

    def __init__(self, lang: str):
        self.lang = normalize_lang(lang)

    def __call__(self, key: str, **kwargs: Any) -> str:
        return translate(key, self.lang, **kwargs)

    @property
    def short(self) -> str:
        return brand_short(self.lang)

    @property
    def full(self) -> str:
        return brand_full(self.lang)
