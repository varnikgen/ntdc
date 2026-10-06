# Что исправлено в 0.2.0 и как этим пользоваться

Ниже — каждая проблема из аудита и конкретное изменение. После деплоя обязательно: новый `.env` , новые пароли, перевыпуск сертификата, `podman-compose up --build -d` .

---

## 1. Безопасность

### 1.1 Открытый `/provision` (слив SIP-паролей)

**Было:** любой, кто угадал MAC, скачивал cfg с паролями.
**Стало:** HTTP Basic на весь `/provision` . Учётки — `PROVISION_USER` / `PROVISION_PASS` . Они же записываются в глобальный cfg как `static.auto_provision.username/password` , чтобы трубки ходили повторно уже с паролем.

**Что сделать вам:** прописать те же учётки на телефоне или в DHCP. Для лаборатории на час можно `PROVISION_AUTH_ENABLED=false` , в проде — никогда.

### 1.2 Открытый `/actions` (подмена IP и статуса)

**Было:** `GET /actions/?mac=...&event=registered` принимался от кого угодно.
**Стало:** обязательный `?token=` = `ACTION_URI_TOKEN` . Неверный токен → 403.

Токен подставляется в Action URL при первом старте (`app/defaults.py` ).

**Что сделать вам:** в Global Config проверьте, что URL событий содержат ваш токен. Если БД уже была — либо прогоните `python fix_db.py` (допишет только пустые ключи), либо поправьте URL вручную.

### 1.3 Секреты в git и дефолтные пароли

**Было:** `ChangeMe123!` , `Cgtwbfkbcbn01` в compose, `admin/admin` на трубках.
**Стало:**

* приложение **не стартует** , если пароль пустой или из чёрного списка;
* пароль админки только из .env ;
* из podman-compose.yml секреты убраны;
* пароль веб-UI телефона задаётся в карточке устройства.

**Что сделать вам:** `cp .env.example .env` и сгенерировать:

```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Смените `Cgtwbfkbcbn01` везде, где он мог остаться (git history тоже считать скомпрометированным).

### 1.4 Пароли в HTML и в SQL-логах

**Было:** `<input type="password" value="реальный пароль">` , `DEBUG=True` , `echo=True` .
**Стало:** пустой password-input = «не менять»; `DEBUG=false` ; SQL-echo только при DEBUG.

### 1.5 Сравнение паролей и brute-force

Constant-time `hmac.compare_digest` + lockout 5 неудач / 60 секунд с IP ( `X-Forwarded-For` берётся только первый hop от nginx, `$remote_addr` ).

### 1.6 CSRF

Все POST админки требуют заголовок `X-CSRF-Token` , равный cookie `ntdc_csrf` . В `base.html` `fetch` и HTMX подставляют его сами. `/provision` и `/actions` исключены.

### 1.7 AutoP `verify=False`

Оставлен по умолчанию: у Yealink самоподписанный сертификат веб-UI. Включается проверкой через `AUTOP_VERIFY_SSL=true` , если вы поставили нормальный cert на трубки.

---

## 2. Сломанный основной сценарий

### 2.1 Нельзя создать телефон

**Было:** кнопка вела на `/phones/new` → 404, Action URI неизвестный MAC игнорировал.
**Стало:** форма `/phones/new` , POST `/phones/` , удаление устройства.

При `AUTO_ENROLL=true` неизвестный MAC создаётся и с Action URL, и с запроса `{mac}.cfg` .

### 2.2 Custom config не сохранялся

JS слал JSON в `custom_config` , бэкенд парсил поля `custom_*` и писал кашу.

Теперь бэкенд читает JSON `custom_config` . В форме поля с классами `cfg-key` / `cfg-val` , без кривых имён.

### 2.3 `default_config` модели не попадал в cfg

Шаблон ждал `model_specific_settings` , код клал ключи в корень.

Рендер идёт по `model_default_config` .

### 2.4 802.1x не включался

В cfg не было `static.network.802_1x.enable = 1` . Добавлено, плюс поле EAP-MD5 пароля вместо пустой строки.

### 2.5 HTMX не был подключён

В `base.html` добавлен `htmx.min.js` . Переключатель Override DSS Keys снова подгружает таблицу.

### 2.6 Boolean в Global Config нельзя было выключить

Unchecked checkbox не уходит в POST. Теперь перед каждым switch стоит hidden `value=0` ; если галочка снята, в БД пишется `0` .

### 2.7 Нет UI для AutoP-учёток телефона

В карточке устройства: Admin Username / Password и редактируемый IP.

---

## 3. Генерация конфигов

| Было | Стало |
| --- | --- |
| Глобальный cfg через HTML-escaping Jinja | Отдельный jinja_env без autoescape, фильтр cfg |
| SIP-пароль без кавычек | quote_cfg кавычит пробелы и спецсимволы |
| overwrite_mode = 0 | BOOT_OVERWRITE_MODE (дефолт 1 ) |
| Fallback IP 10.30.30.30 | Нет хардкода, URL из PUBLIC_BASE_URL |
| Неизвестный MAC → 500 | 404 или auto-enroll |
| MAC из UA склеивался с версией прошивки | Парсер не удаляет пробелы из всего UA |

---

## 4. Данные и надёжность

* PRAGMA foreign_keys=ON .
* Аддитивные миграции app/database.py:run_migrations() (новые колонки на живой SQLite).
* Удаление аккаунта снимает его с телефонов, удаление модели блокируется если есть устройства.
* Дашборд использует Depends(get_db) — сессия закрывается.
* Фоновый цикл: rollback + close в finally .
* DND ставится по Action URL event=dnd_on / dnd_off .
* fix_db.py больше не делает DELETE FROM global_config — только дописывает пустые ключи.

---

## 5. Деплой

* Хост больше не зашит: nginx server_name _; , URL — PUBLIC_BASE_URL .
* .env.example обязателен, .env в .gitignore .
* scripts/gen-ssl.sh пишет nginx/ssl/ntdc.crt + ntdc.key .
* Есть и Dockerfile , и Containerfile .
* Healthcheck на /health .
* Контейнер от uid 1000, pip без --trusted-host .
* Добавлен LICENSE (MIT).

---

## Порядок обновления с 0.1.x

1. Остановить контейнеры, снять копию data/ntdc.db .
2. Выложить новый код.
3. Создать .env из .env.example (новые секреты, не старые из git).
4. mkdir -p data nginx/ssl && sh scripts/gen-ssl.sh your.hostname .
5. chown 1000:1000 data (или chmod 0777 data в лабе).
6. podman-compose up --build -d .
7. Зайти в Global Config: URL провижининга, Action URL с токеном, IPv6=off если нужно.
8. На каждой трубке прописать provision username/password.
9. Прогнать pytest на стенде разработки.

---

## 0.2.10

### Детекция модели

- Централизована в `app/security.py` → `detect_model_from_ua()`.
- Поддерживает широкий набор популярных моделей (T4x/T5x/T7x, W70/W80, CP, VP и др.).
- Используется и при auto-enroll через `/provision`, и через `/actions`.
- Старый хардкод в `provisioning.py` удалён.

### Документация и CI

- README переписан: актуальная структура, возможности, без лабораторных IP.
- Добавлен `.github/workflows/ci.yml` (pytest на push/PR).
- Версия приложения: 0.2.10.
