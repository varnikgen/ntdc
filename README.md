## NCDC (Network Configuration & Device Control)

Система автопровижининга и управления IP-телефонами **Yealink**.

Веб-админка, иерархические cfg-файлы (global → model → device), HTTPS, 802.1x, DSS-клавиши, AutoP push, журнал аудита, auto-enroll по MAC.

**Версия 0.2.10.** Подробности исправлений — в [FIXES.md](FIXES.md).

### Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Uvicorn |
| Frontend | Jinja2, HTMX, Bootstrap 5 |
| БД | SQLite (WAL + foreign_keys) |
| Proxy | Nginx |
| Контейнеры | Podman / Docker Compose |

### Быстрый старт

```bash
git clone <your-repo-url>
cd ncdc-qwen

cp .env.example .env
# Обязательно задайте:
#   NCDC_ADMIN_PASS, SECRET_KEY, PROVISION_PASS, ACTION_URI_TOKEN, PUBLIC_BASE_URL

mkdir -p data nginx/ssl
chmod 0777 data   # или chown 1000:1000 data  (контейнер работает от uid 1000)

# Самоподписанный сертификат для лаборатории:
sh scripts/gen-ssl.sh ncdc.example.com

podman-compose up --build -d
# или: docker compose up --build -d
```

Без заполненного `.env` приложение **не стартует** — специально, чтобы не поднять прод с дефолтными паролями.

#### Проблемы с сетью при сборке (rootless Podman)

Если `pip install` падает с `Network is unreachable` / `Errno 101`:

**A. Сеть хоста на время сборки**

```bash
podman build --network=host -t ncdc-qwen .
podman-compose up -d
```

В `podman-compose.yml` для `build` уже стоит `network: host`.

**B. Офлайн-колёса (Windows → Linux)**

```powershell
.\scripts\download-linux-wheels.ps1
```

Скопируйте `vendor/py311-linux/` на сервер. Сборка больше не ходит в интернет.

### Запуск без контейнеров (Windows / dev)

```powershell
# в .env:
# PUBLIC_BASE_URL=http://your-host:8000

.\scripts\run-windows.ps1
```

- Админка: `http://localhost:8000/`
- Health: `curl http://localhost:8000/health`
- Логин: `NCDC_ADMIN_USER` / `NCDC_ADMIN_PASS` из `.env`

Проверка, кто слушает порт: `powershell -File .\scripts\where-is-ncdc.ps1`

### Первичная настройка телефонов

1. **Global Config** — URL провижининга, часовой пояс, Action URL (токен подставляется при первом старте).
2. **Model Config** — создайте модель (T46U, T54W…), прошивку, 802.1x.
3. **Account List** — SIP-аккаунты.
4. **Device List** — добавьте MAC вручную **или** включите `AUTO_ENROLL=true` и дождитесь первого запроса телефона.

На телефоне (или через DHCP option 66/43):

- Server URL: `https://ncdc.example.com/provision/`
- Username / password: `PROVISION_USER` / `PROVISION_PASS`

Без этих учёток cfg не отдаётся.

### Переменные окружения

См. `.env.example`. Критичные:

| Переменная | Назначение |
|---|---|
| `PUBLIC_BASE_URL` | URL, который телефоны используют для cfg и Action URL |
| `NCDC_ADMIN_PASS` | Пароль админки (дефолты из git отклоняются) |
| `PROVISION_PASS` | HTTP Basic для `/provision` |
| `ACTION_URI_TOKEN` | Секрет в `?token=` на `/actions` |
| `AUTO_ENROLL` | Создавать телефон при первом cfg / Action URL |
| `BOOT_OVERWRITE_MODE` | `1` — централизованные настройки перекрывают локальные |
| `PROVISION_BOOTSTRAP` | `true` — отдавать cfg без Basic после заводского сброса |

### Безопасность

- `/provision` закрыт HTTP Basic (`PROVISION_USER` / `PROVISION_PASS`).
- `/actions` принимает запросы только с верным `token`.
- Админка: Basic Auth + CSRF + lockout после 5 неверных попыток.
- `DEBUG=false` по умолчанию, SQL-echo выключен.
- Пароли SIP в формах не отображаются; пустое поле = оставить прежний.
- Контейнер запускается от пользователя `ncdc` (uid 1000).
- Приложение не стартует с пустыми / известными слабыми паролями.

### Структура проекта

```text
ncdc-qwen/
├── app/
│   ├── main.py              # Точка входа FastAPI + lifespan
│   ├── config.py            # Settings из .env
│   ├── models.py            # SQLAlchemy: Phone, Account, PhoneModel, …
│   ├── security.py          # MAC, quote_cfg, detect_model, throttle
│   ├── database.py          # Engine, миграции
│   ├── defaults.py          # Стартовый global cfg + Action URL
│   ├── middleware/          # Basic Auth, CSRF
│   ├── routers/             # phones, accounts, provisioning, actions, …
│   ├── services/            # config_builder, linekeys, push, audit
│   ├── templates/           # Админка (Jinja2 + HTMX) + provision/*.j2
│   └── static/
├── configs/                 # Вспомогательные данные
├── nginx/nginx.conf
├── scripts/                 # gen-ssl, run-windows, download-wheels
├── tests/
├── vendor/py311-linux/      # Опциональные offline-колёса
├── .env.example
├── Dockerfile / Containerfile
├── podman-compose.yml
├── requirements.txt
└── FIXES.md
```

### Возможности

- Иерархическая генерация cfg: global → model (`$PN.cfg`) → device (`$MAC.cfg`)
- Auto-enroll неизвестных MAC + автоопределение модели из User-Agent
- 802.1x (EAP-MD5 / TLS / PEAP / TTLS)
- DSS / Line keys с override на уровне устройства
- AutoP push (с учётом самоподписанных cert трубок)
- Журнал аудита с ротацией
- Экспорт/импорт cfg (`yealink_export.py`, `yealink_bulk_export.py`)

### Тесты

```bash
pip install -r requirements-dev.txt
pytest
```

### Резервное копирование

```bash
cp data/ncdc.db backups/ncdc_$(date +%Y%m%d).db
```

Файл БД содержит SIP-пароли — храните бэкапы как секрет.

### Лицензия

MIT. См. [LICENSE](LICENSE).
