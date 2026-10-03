"""Импорт экспортированных cfg-файлов Yealink (*-all.cfg).

Логика: парсим ключи, вычитаем совпадающее с global_config,
account.* превращаем в объекты Account (ищем по username или создаём),
linekey.* превращаем в custom_dss_keys,
остаток — в phone.custom_config.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.models import Phone, Account, GlobalConfig
from app.security import normalize_mac

logger = logging.getLogger("ncdc.cfg_import")

LINEKEY_RE = re.compile(r"^linekey\.(\d+)\.(type|line|value|extension|label|enable)$")
ACCOUNT_RE = re.compile(
    r"^account\.(\d+)\.(enable|label|display_name|auth_name|user_name|password|"
    r"sip_server\.1\.(address|port|transport_type)|"
    r"codec\.\d+\.(enable|payload_type|priority))$"
)
MAC_IN_NAME_RE = re.compile(r"(?<![0-9A-Fa-f.:])([0-9A-Fa-f]{12})(?![0-9A-Fa-f])")

IMPORT_IGNORE_PREFIXES = (
    "static.auto_provision.",
    "action_url.",
    "features.action_uri",
    "account.",  # обрабатываем отдельно
)

# Маппинг transport_type: cfg (0-3) -> DB (udp/tcp/tls)
TRANSPORT_MAP = {"0": "udp", "1": "tcp", "2": "tls", "3": "naptr"}


def parse_yealink_cfg(text: str) -> dict:
    """Плоский словарь key->value из cfg-файла Yealink."""
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def mac_from_filename(filename: str):
    m = MAC_IN_NAME_RE.search(filename)
    return normalize_mac(m.group(1)) if m else None


def parse_accounts(parsed: dict) -> dict:
    """Группирует account.N.* в словарь {N: {...}}."""
    accounts: dict = {}
    for key, value in parsed.items():
        m = ACCOUNT_RE.match(key)
        if not m:
            continue
        n = int(m.group(1))
        field = m.group(2)
        acc = accounts.setdefault(n, {"line": n})

        # Убираем префикс sip_server.1. и codec.N.
        if field.startswith("sip_server.1."):
            acc.setdefault("sip", {})[field[len("sip_server.1."):]] = value
        elif field.startswith("codec."):
            # кодеки пока не импортируем — используем дефолты
            pass
        else:
            acc[field] = value
    return accounts


def find_or_create_account(db: Session, raw: dict) -> Account:
    """Ищет Account по username или создаёт новый."""
    username = raw.get("user_name") or raw.get("auth_name")
    if not username:
        # Аккаунт без логина — пропускаем
        return None

    acc = db.query(Account).filter(Account.username == username).first()
    if acc:
        # Обновляем пароль, если он поменялся
        new_pass = raw.get("password")
        if new_pass and new_pass != acc.password:
            acc.password = new_pass
            db.commit()
        return acc

    # Создаём новый аккаунт
    sip = raw.get("sip", {})
    transport_cfg = sip.get("transport_type", "0")
    transport = TRANSPORT_MAP.get(transport_cfg, "udp")

    acc = Account(
        name=raw.get("label") or raw.get("display_name") or username,
        username=username,
        password=raw.get("password") or "",
        display_name=raw.get("display_name") or username,
        sip_server=sip.get("address") or "",
        sip_port=int(sip.get("port") or 5060),
        transport=transport,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    logger.info("Created account: %s (id=%s)", acc.username, acc.id)
    return acc


def split_personal(parsed: dict, global_settings: dict):
    """Возвращает (custom_config, dss_keys). Account.* уже обработан отдельно."""
    custom = {}
    linekeys: dict = {}

    for key, value in parsed.items():
        if key.startswith(IMPORT_IGNORE_PREFIXES):
            continue
        g = global_settings.get(key)
        if g is not None and str(g) == str(value):
            continue

        lk = LINEKEY_RE.match(key)
        if lk:
            n, field = int(lk.group(1)), lk.group(2)
            linekeys.setdefault(n, {"line": n})[field] = value
            continue
        custom[key] = value

    dss = []
    for n, f in sorted(linekeys.items()):
        try:
            ktype = int(f.get("type") or 0)
        except (TypeError, ValueError):
            ktype = 0
        if ktype == 0:
            continue
        acc = f.get("line", "1")
        dss.append({
            "line": n,
            "type": ktype,
            "account": int(acc) if str(acc).isdigit() else 1,  # это НОМЕР ЛИНИИ, не ID
            "value": f.get("value", ""),
            "extension": f.get("extension", ""),
            "label": f.get("label", ""),
        })
    return custom, dss


def import_cfg_file(db: Session, filename: str, text: str) -> dict:
    mac = mac_from_filename(filename)
    if not mac:
        return {"file": filename, "ok": False, "error": "MAC не найден в имени файла"}

    parsed = parse_yealink_cfg(text)
    if not parsed:
        return {"file": filename, "ok": False, "error": "Файл пустой или не распознан"}

    g = db.query(GlobalConfig).first()
    global_settings = g.settings if g and g.settings else {}

    # 1. Импортируем аккаунты
    raw_accounts = parse_accounts(parsed)
    account_ids = []
    primary_id = None
    accounts_imported = 0

    for line_no in sorted(raw_accounts.keys()):
        raw = raw_accounts[line_no]
        # Пропускаем отключённые аккаунты
        if raw.get("enable") == "0":
            continue

        acc = find_or_create_account(db, raw)
        if acc:
            account_ids.append(acc.id)
            # Первая активная линия = primary
            if primary_id is None:
                primary_id = acc.id
            accounts_imported += 1

    # 2. Импортируем custom_config и DSS
    custom, dss = split_personal(parsed, global_settings)

    # 3. Создаём или обновляем телефон
    phone = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
    created = phone is None
    if created:
        phone = Phone(mac=mac, status="unregistered")
        db.add(phone)

    phone.custom_config = custom
    phone.custom_dss_keys = dss
    phone.override_dss_keys = bool(dss)
    phone.account_ids = account_ids
    phone.primary_account_id = primary_id

    db.commit()
    db.refresh(phone)

    logger.info(
        "Imported %s: mac=%s created=%s custom=%d dss=%d accounts=%d",
        filename, mac, created, len(custom), len(dss), accounts_imported
    )
    return {
        "file": filename, "ok": True, "mac": mac,
        "created": created,
        "custom_keys": len(custom),
        "dss_keys": len(dss),
        "accounts": accounts_imported,
    }
