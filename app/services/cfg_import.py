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

from app.models import Phone, Account, GlobalConfig, PhoneModel
from app.security import normalize_mac, detect_model_from_ua, KNOWN_MODELS

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
        if value.lower() == "none":
            value = ""          # Yealink экспортирует литерал None для пустых значений
        if key:
            out[key] = value
    return out


def mac_from_filename(filename: str):
    m = MAC_IN_NAME_RE.search(filename)
    return normalize_mac(m.group(1)) if m else None


# Экспорт yealink_bulk_export: 10.30.16.10_44DBD222CF31_T31P-all.cfg
IP_IN_NAME_RE = re.compile(
    r"(?<![\d])((?:\d{1,3}\.){3}\d{1,3})(?![\d])"
)


def ip_from_filename(filename: str) -> str | None:
    """Достаёт IPv4 из имени файла (обычно первый токен перед MAC)."""
    if not filename:
        return None
    name = filename.rsplit("/", 1)[-1]
    m = IP_IN_NAME_RE.search(name)
    if not m:
        return None
    ip = m.group(1)
    parts = ip.split(".")
    try:
        if len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts):
            return ip
    except ValueError:
        return None
    return None


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
    resolved_model = resolve_model_name(db, None, filename, parsed)
    if resolved_model:
        phone.model_name = resolved_model
    ip = ip_from_filename(filename)
    if ip:
        phone.ip_address = ip

    db.commit()
    db.refresh(phone)

    logger.info(
        "Imported %s: mac=%s created=%s custom=%d dss=%d accounts=%d model=%s",
        filename, mac, created, len(custom), len(dss), accounts_imported, phone.model_name,
    )
    return {
        "file": filename, "ok": True, "mac": mac,
        "created": created,
        "custom_keys": len(custom),
        "dss_keys": len(dss),
        "accounts": accounts_imported,
        "model": phone.model_name,
    }


def detect_model_from_filename(filename: str) -> str | None:
    """10.30.16.10_44DBD222CF31_T31P-all.cfg / T46U_001565....cfg / SIP-T46U-....cfg"""
    if not filename:
        return None
    name = filename.rsplit("/", 1)[-1]
    # убираем -all.cfg / .cfg
    stem = re.sub(r"(?i)-all\.cfg$|\.cfg$", "", name)
    name_upper = stem.upper()
    for model in sorted(KNOWN_MODELS, key=len, reverse=True):
        # целый токен после MAC: _T31P в конце
        if re.search(r"(?:^|[_\-])" + re.escape(model.upper()) + r"(?:$|[_\-])", name_upper):
            return model.upper()
        if model.upper() in name_upper:
            return model.upper()
    m = re.search(
        r"(?:SIP[-_])?([A-Z]?T\d{2}[A-Z]?\d?[A-Z]?|W\d{2}[A-Z]?|CP\d{3}|VP[-_]?T?\d{2}[A-Z]?)",
        name_upper,
    )
    if m:
        return m.group(1).replace("_", "-")
    return None


def detect_model_from_cfg(parsed: dict) -> str | None:
    """Ищем модель в значениях cfg (product name, firmware path, comments-as-keys)."""
    if not parsed:
        return None
    # Склеиваем несколько характерных полей + все значения (ограниченно)
    candidates = []
    for key in (
        "phone_setting.product_name",
        "static.auto_provision.custom_protect.pn",
        "firmware.url",
        "static.firmware.url",
        "wui.product_name",
    ):
        if key in parsed and parsed[key]:
            candidates.append(str(parsed[key]))
    # также пробуем весь текст значений (короткий скан)
    blob = " ".join(candidates)
    if not blob:
        # fallback: первые 50 значений
        blob = " ".join(str(v) for v in list(parsed.values())[:50] if v)
    found = detect_model_from_ua(blob)
    if found:
        return found
    blob_u = blob.upper()
    for model in sorted(KNOWN_MODELS, key=len, reverse=True):
        if model.upper() in blob_u:
            return model.upper()
    return None


def resolve_model_name(
    db: Session,
    explicit: str | None,
    filename: str,
    parsed: dict,
) -> str | None:
    """Явная модель из формы → имя файла → содержимое cfg. Создаёт PhoneModel при необходимости."""
    model = (explicit or "").strip().upper() or None
    if not model:
        model = detect_model_from_filename(filename)
    if not model:
        model = detect_model_from_cfg(parsed)
    if not model:
        return None
    # убедимся, что модель есть в справочнике
    row = db.query(PhoneModel).filter(PhoneModel.name == model).first()
    if not row:
        db.add(PhoneModel(name=model))
        db.flush()
        logger.info("Auto-created PhoneModel %s during import", model)
    return model

def import_batch(db: Session, files: list, model_name: str | None, promote_common: bool) -> dict:
    """Пакетный импорт с продвижением общих ключей в Global Config.

    files: список кортежей (filename, text)
    """
    report = []
    parsed_all = []

    for filename, text in files:
        mac = mac_from_filename(filename)
        if not mac:
            report.append({"file": filename, "ok": False, "error": "MAC не найден в имени файла"})
            continue
        parsed = parse_yealink_cfg(text)
        if not parsed:
            report.append({"file": filename, "ok": False, "error": "Файл пустой или не распознан"})
            continue
        parsed_all.append((filename, mac, parsed))

    # Настройки выбранной модели — для вычитания модельных ключей
    model_settings = {}
    if model_name:
        m = db.query(PhoneModel).filter(PhoneModel.name == model_name).first()
        if m and m.default_config:
            model_settings = m.default_config

    g = db.query(GlobalConfig).first()
    if not g:
        g = GlobalConfig(settings={})
        db.add(g)
        db.commit()
    global_settings = dict(g.settings or {})

    # Остаток каждого файла: без account.*, linekey.* и игнорируемых префиксов
    remainders = []
    for filename, mac, parsed in parsed_all:
        rem = {
            k: v for k, v in parsed.items()
            if not k.startswith(IMPORT_IGNORE_PREFIXES)
            and not LINEKEY_RE.match(k)
            and v != ""                      # пустые значения информации не несут
        }
        remainders.append(rem)

    # 1. Продвижение общих ключей в Global Config
    promoted, conflicts = [], []
    if promote_common and remainders:
        common = {
            k: v for k, v in remainders[0].items()
            if all(r.get(k) == v for r in remainders)
        }
        for k, v in common.items():
            cur = global_settings.get(k)
            if cur is None:
                global_settings[k] = v
                promoted.append(k)
            elif str(cur) != str(v):
                conflicts.append(f"{k}: global={cur}, файл={v} (оставлено персонально)")
        if promoted:
            g.settings = global_settings
            db.commit()
            logger.info("Promoted %d common keys to Global Config: %s", len(promoted), promoted)

    # 2. Персональный импорт каждого файла
    for (filename, mac, parsed), rem in zip(parsed_all, remainders):
        raw_accounts = parse_accounts(parsed)
        account_ids, primary_id, accounts_imported = [], None, 0
        for line_no in sorted(raw_accounts):
            raw = raw_accounts[line_no]
            if raw.get("enable") == "0":
                continue
            acc = find_or_create_account(db, raw)
            if acc:
                account_ids.append(acc.id)
                if primary_id is None:
                    primary_id = acc.id
                accounts_imported += 1

        # Дифференцируем остаток против global (уже с promoted) и model
        custom, dss = _diff_remainder(rem, global_settings, model_settings, parsed)

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
        resolved_model = resolve_model_name(db, model_name, filename, parsed)
        if resolved_model:
            phone.model_name = resolved_model
        elif not phone.model_name:
            phone.model_name = None
        ip = ip_from_filename(filename)
        if ip:
            phone.ip_address = ip

        db.commit()
        db.refresh(phone)
        report.append({
            "file": filename, "ok": True, "mac": mac, "created": created,
            "custom_keys": len(custom), "dss_keys": len(dss),
            "accounts": accounts_imported,
            "model": phone.model_name,
            "ip": phone.ip_address,
        })

    ok = sum(1 for r in report if r.get("ok"))
    return {
        "status": "success", "imported": ok, "total": len(report),
        "report": report, "promoted": promoted, "conflicts": conflicts,
    }

def _diff_remainder(rem: dict, global_settings: dict, model_settings: dict, parsed: dict):
    """Оставляет в custom только то, чего нет ни в global, ни в model; linekey -> dss."""
    custom = {}
    linekeys = {}
    for key, value in rem.items():
        g = global_settings.get(key)
        if g is not None and str(g) == str(value):
            continue
        m = model_settings.get(key)
        if m is not None and str(m) == str(value):
            continue
        lk = LINEKEY_RE.match(key)
        if lk:
            n, field = int(lk.group(1)), lk.group(2)
            linekeys.setdefault(n, {"line": n})[field] = value
            continue
        custom[key] = value

    # linekey.* пришли из rem без значений global/model — берём их из parsed целиком
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
            "line": n, "type": ktype,
            "account": int(acc) if str(acc).isdigit() else 1,
            "value": f.get("value", ""), "extension": f.get("extension", ""),
            "label": f.get("label", ""),
        })
    return custom, dss
