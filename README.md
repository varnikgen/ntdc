# КУСТ / NTDC

**КУСТ** — Конфигуратор устройств сетевой телефонии  
**NTDC** — Network Telephony Device Configurator

> Прежнее кодовое имя репозитория: КУСТ (внутренние пути `ncdc-*` сохранены).

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
cp .env.example .env   # задать SECRET_KEY, КУСТ_ADMIN_*, PROVISION_*
podman-compose up --build -d
# UI: http://host:8080/login
```

Переменные — в `.env` / `app/config.py` (`КУСТ_ADMIN_USER/PASS`, `SECRET_KEY`, `PROVISION_*`, `PUBLIC_BASE_URL`, `ACTION_URI_TOKEN`, …).

## Роли

| Роль | Доступ |
|------|--------|
| admin | всё, включая Global Config, модели, пользователи, аудит |
| operator | Dashboard, устройства, SIP-аккаунты |
| viewer | то же, только GET |

Пользователи сервиса: **Система → Пользователи** (admin). Fallback: `КУСТ_ADMIN_*` из `.env`.

## Импорт cfg

**Global Config → Импорт.** Имена вида `10.30.16.10_44DBD222CF31_T31P-all.cfg`:

- MAC, IP, модель из имени (и/или содержимого)
- SIP-аккаунты, personal keys, DSS
- опционально promote общих ключей в Global

## Линии SIP (`phone_accounts`)

Связь телефон ↔ аккаунты хранится в таблице `phone_accounts` (`line_no` = номер линии Yealink).  
JSON `phones.account_ids` синхронизируется для совместимости; при старте выполняется миграция.

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
