"""Импорт SIP-аккаунтов из CSV-выгрузки FreePBX (Extensions).

Маппинг (минимум для Account):
  extension  → username
  secret     → password  (колонка password в выгрузке часто пустая)
  name       → name
  description / name → display_name
  transport  → transport (пусто → udp)

sip_server и sip_port задаются вызывающим кодом (форма импорта).
При совпадении username — обновление существующей записи.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import Account

logger = logging.getLogger("ntdc.freepbx_csv")

# Нормализация transport из FreePBX / пустых значений
_TRANSPORT_MAP = {
    "": "udp",
    "udp": "udp",
    "tcp": "tcp",
    "tls": "tls",
    "0": "udp",  # иногда числовые коды
    "1": "tcp",
    "2": "tls",
}


def _norm_transport(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    return _TRANSPORT_MAP.get(key, "udp")


def parse_freepbx_csv(text: str) -> list[dict[str, str]]:
    """Парсит CSV FreePBX, возвращает список dict только с нужными полями.

    Пропускает строки без extension. Пароль берёт из secret, fallback на password.
    """
    # utf-8-sig снимает BOM, который иногда добавляет Excel/FreePBX
    stream = io.StringIO(text.lstrip("\ufeff"))
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        return []

    # нормализуем имена колонок (нижний регистр, без пробелов)
    field_map = {f: f.strip().lower() for f in reader.fieldnames}

    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {field_map[k]: (v or "").strip() for k, v in raw.items() if k in field_map}
        extension = row.get("extension") or row.get("user") or ""
        if not extension:
            continue
        secret = row.get("secret") or row.get("password") or ""
        name = row.get("name") or extension
        description = row.get("description") or name
        transport = _norm_transport(row.get("transport"))

        rows.append(
            {
                "username": extension,
                "password": secret,
                "name": name,
                "display_name": description,
                "transport": transport,
            }
        )
    return rows


def import_accounts_from_csv(
    db: Session,
    text: str,
    sip_server: str,
    sip_port: int = 5060,
) -> dict[str, Any]:
    """Создаёт/обновляет Account из CSV.

    Returns:
        {
          "total": int,       # строк в CSV с extension
          "created": int,
          "updated": int,
          "skipped": int,     # без пароля при create, или пустой username
          "errors": list[str],
        }
    """
    sip_server = (sip_server or "").strip()
    if not sip_server:
        return {
            "total": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": ["sip_server обязателен"],
        }

    try:
        port = int(sip_port)
    except (TypeError, ValueError):
        port = 5060
    if port < 1 or port > 65535:
        port = 5060

    parsed = parse_freepbx_csv(text)
    result: dict[str, Any] = {
        "total": len(parsed),
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
    }

    for item in parsed:
        username = item["username"]
        password = item["password"]
        name = item["name"]
        display_name = item["display_name"]
        transport = item["transport"]

        existing = db.query(Account).filter(Account.username == username).first()
        if existing:
            existing.name = name
            existing.display_name = display_name
            existing.sip_server = sip_server
            existing.sip_port = port
            existing.transport = transport
            if password:
                existing.password = password
            # если пароль пустой при update — оставляем старый
            result["updated"] += 1
            continue

        if not password:
            result["skipped"] += 1
            result["errors"].append(f"{username}: нет пароля (secret), пропуск create")
            continue

        account = Account(
            name=name,
            sip_server=sip_server,
            sip_port=port,
            transport=transport,
            username=username,
            password=password,
            display_name=display_name,
            dss_keys=[],
        )
        db.add(account)
        result["created"] += 1

    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("freepbx csv import commit failed")
        result["errors"].append(f"commit failed: {exc}")
        result["created"] = 0
        result["updated"] = 0

    return result
