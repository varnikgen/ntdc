"""Общие хелперы разбора полей форм (JSON из FormData)."""

from __future__ import annotations

import json
from typing import Any


def parse_json_field(raw: Any, default: Any = None) -> Any:
    """JS кладёт JSON-строку в FormData; сломанный JSON → default."""
    if raw is None or raw == "":
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def parse_json_list(raw: Any) -> list:
    data = parse_json_field(raw, [])
    return data if isinstance(data, list) else []


def parse_json_dict(raw: Any) -> dict:
    data = parse_json_field(raw, {})
    return data if isinstance(data, dict) else {}
