"""Импорт экспортированных cfg-файлов Yealink (*-all.cfg).

Логика: парсим все ключи, вычитаем совпадающие с global_config,
остаток (персональное) кладём в phone.custom_config,
linekey.* превращаем в структурированные custom_dss_keys.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.models import Phone, GlobalConfig
from app.security import normalize_mac

logger = logging.getLogger("ncdc.cfg_import")

LINEKEY_RE = re.compile(r"^linekey\.(\d+)\.(type|line|value|extension|label|enable)$")
MAC_IN_NAME_RE = re.compile(r"(?<![0-9A-Fa-f.:])([0-9A-Fa-f]{12})(?![0-9A-Fa-f])")

# Ключи, которые всегда управляются централизованно — не импортируем,
# даже если на трубке они отличаются (иначе телефон вернётся на старый сервер)
IMPORT_IGNORE_PREFIXES = (
    "static.auto_provision.",
    "action_url.",
    "features.action_uri",
)


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


def split_personal(parsed: dict, global_settings: dict):
    """Возвращает (custom_config, dss_keys) — только то, чего нет в global."""
    custom = {}
    linekeys: dict = {}

    for key, value in parsed.items():
        if key.startswith(IMPORT_IGNORE_PREFIXES):
            continue
        g = global_settings.get(key)
        if g is not None and str(g) == str(value):
            continue  # совпадает с глобальным — не дублируем

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
            "account": int(acc) if str(acc).isdigit() else 1,
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
    custom, dss = split_personal(parsed, global_settings)

    phone = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
    created = phone is None
    if created:
        phone = Phone(mac=mac, status="unregistered")
        db.add(phone)

    phone.custom_config = custom
    phone.custom_dss_keys = dss
    phone.override_dss_keys = bool(dss)
    db.commit()
    db.refresh(phone)

    logger.info("Imported %s: mac=%s created=%s custom=%d dss=%d",
                filename, mac, created, len(custom), len(dss))
    return {
        "file": filename, "ok": True, "mac": mac,
        "created": created, "custom_keys": len(custom), "dss_keys": len(dss),
    }