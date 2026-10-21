# КУСТ / NTDC

**КУСТ** — Конфигуратор устройств сетевой телефонии  
**NTDC** — Network Telephony Device Configurator

> Прежнее кодовое имя репозитория: NCDC (внутренние пути `ncdc-*` сохранены).

Провижининг и управление телефонами **Yealink** (SIP): boot/cfg, Action URL, AutoP, SIP-аккаунты, импорт bulk-export.

## Возможности

- Иерархия cfg: `y000000000000.cfg` (global) → `$PN.cfg` (модель) → `$MAC.cfg` (телефон)
- Boot-файл с include и Auth
- Action URL → статус online/dnd/offline, last_seen, IP
- AutoP push после сохранения телефона
- Импорт cfg из `yealink_bulk_export` (`IP_MAC_MODEL-all.cfg`)
- Роли: **admin** / **operator** (устройства + SIP) / **viewer** (чтение)
- Логин по сессии (`/login`), HTTP Basic для скриптов
- Offline UI (Bootstrap/HTMX локально), поиск, пагинация, сортировка, фильтр статуса

## Быстрый старт (Podman)

```bash
cp .env.example .env   # задать SECRET_KEY, NCDC_ADMIN_*, PROVISION_*
podman-compose up --build -d
# UI: http://host:8080/login
```

Переменные — в `.env` / `app/config.py` (`NCDC_ADMIN_USER/PASS`, `SECRET_KEY`, `PROVISION_*`, `PUBLIC_BASE_URL`, `ACTION_URI_TOKEN`, …).

## Роли

| Роль | Доступ |
|------|--------|
| admin | всё, включая Global Config, модели, пользователи, аудит |
| operator | Dashboard, устройства, SIP-аккаунты |
| viewer | то же, только GET |

Пользователи сервиса: **Система → Пользователи** (admin). Fallback: `NCDC_ADMIN_*` из `.env`.

## Импорт cfg

**Глобальные настройки → Импорт** (только admin).  
Поддерживаются файлы экспорта `yealink_bulk_export` и обычные `*-all.cfg` / `$MAC.cfg`.

### Имя файла

Рекомендуемый формат:

```text
10.30.16.10_44DBD222CF31_T31P-all.cfg
```

| Часть имени | Что извлекается |
|-------------|-----------------|
| `10.30.16.10` | IP телефона |
| `44DBD222CF31` | MAC (12 hex) |
| `T31P` | модель (создаётся в справочнике, если нет) |

MAC обязателен (в имени или распознаваемый в содержимом). Без MAC файл пропускается.

### SIP-аккаунты

Из ключей `account.N.*` создаются или обновляются записи **SIP-аккаунты**:

| Ключ Yealink | Поле в сервисе |
|--------------|----------------|
| `account.N.user_name` / `auth_name` | username (уникальный ключ поиска) |
| `account.N.password` | password |
| `account.N.label` / `display_name` | name / display_name |
| `account.N.sip_server.1.address` | sip_server |
| `account.N.sip_server.1.port` | sip_port |
| `account.N.sip_server.1.transport_type` | transport (`udp` / `tcp` / `tls`) |

Поведение:

1. Аккаунты с `account.N.enable = 0` **пропускаются**.
2. Поиск существующего аккаунта — по **username**. Если найден — обновляются пароль и SIP-параметры; если нет — создаётся новый.
3. Без `user_name` / `auth_name` линия пропускается.
4. Порядок линий в cfg сохраняется: первая активная линия становится **primary** на телефоне, остальные вешаются как дополнительные линии.
5. Связь телефон ↔ аккаунты пишется в таблицу `phone_accounts` (`line_no` = номер линии Yealink). JSON `phones.account_ids` синхронизируется для совместимости.

### DSS-клавиши (`linekey.*`)

- Из `linekey.N.type/line/value/label/extension` собирается список DSS.
- Список записывается в **`Account.dss_keys` primary-аккаунта** (телефон наследует, `override_dss_keys = false`).
- Если primary нет — DSS остаётся на телефоне (`custom_dss_keys` + override).

### Остальное из cfg

- Персональные ключи (не совпадающие с Global / моделью) → `phone.custom_config`.
- Опция **«Перенести общие параметры в Global»** (`promote`): ключи с одинаковым значением во **всех** загруженных файлах добавляются в Global Config.
- В Global **не** попадают device-UI ключи: `expansion_module.*`, `distinctive_ring_tones.*`, `linekey.*` и т.п. (при открытии Global / импорте такие ключи вычищаются).

### После импорта

1. Проверьте **SIP-аккаунты** — логин, сервер, пароль, DSS.
2. Проверьте **устройства** — MAC, IP, модель, назначенные линии.
3. При необходимости нажмите AutoP / дождитесь следующего цикла провижининга.

## Линии SIP (`phone_accounts`)

Связь телефон ↔ аккаунты: таблица `phone_accounts` (`phone_id`, `line_no`, `account_id`).  
При удалении SIP-аккаунта он снимается со всех линий; если был primary — primary переходит на следующую линию.

## Разработка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload
```

## Структура

```
app/
  main.py              # lifespan, middleware, routers
  models.py            # ORM + phone_accounts
  phone_accounts.py    # get/set/detach линий
  settings_schema.py   # UI schema Global Config
  routers/             # HTTP
  services/            # cfg_import, config_builder, audit, push
  templates/ static/
```

## Безопасность

- Смена дефолтных паролей; сильный `SECRET_KEY`
- Provision Auth отдельно от админки
- CSRF на cookie-сессии; Basic — для автоматизации
- Не открывать админку в интернет без TLS/VPN

## Лицензия

Внутренний проект; при необходимости уточните у владельца репозитория.
