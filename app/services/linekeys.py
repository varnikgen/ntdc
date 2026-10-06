"""Рендер DSS/linekey в текст cfg.

Не через Jinja: {%- съедает перевод строки после пустого label,
и трубка получает `linekey.1.label = linekey.1.line = 1linekey.7.enable = 1`.
"""
from __future__ import annotations

from app.security import quote_cfg

# type 15 = Line/Account, 16 = BLF, 13 = SpeedDial — нужен номер SIP-линии
TYPES_WITH_ACCOUNT = {13, 15, 16}


def render_linekeys_block(dss_keys: list | None, max_keys: int) -> str:
    """Полный блок linekey.1..max_keys.

    Пустой список → пустая строка (заводская раскладка: ключ N = аккаунт N).
    Непустой → заданные ключи + type=0 на остальных, иначе Yealink сам
    повесит account.2 на клавишу 2.
    """
    if not dss_keys:
        return ""

    by_n: dict[int, dict] = {}
    for raw in dss_keys:
        if not isinstance(raw, dict):
            continue
        try:
            n = int(raw.get("line") or 0)
        except (TypeError, ValueError):
            continue
        if n >= 1:
            by_n[n] = raw

    span = max(int(max_keys or 0), max(by_n) if by_n else 0)
    if span < 1:
        return ""

    lines: list[str] = []
    for n in range(1, span + 1):
        raw = by_n.get(n)
        try:
            ktype = int(raw.get("type") or 0) if raw else 0
        except (TypeError, ValueError):
            ktype = 0

        if not raw or ktype == 0:
            lines.append(f"linekey.{n}.type = 0")
            lines.append(f"linekey.{n}.line = 0")
            lines.append(f"linekey.{n}.value =")
            lines.append(f"linekey.{n}.extension =")
            lines.append(f"linekey.{n}.label =")
            lines.append("")
            continue

        try:
            account = int(raw.get("account") if raw.get("account") not in (None, "") else 1)
        except (TypeError, ValueError):
            account = 1
        if ktype not in TYPES_WITH_ACCOUNT:
            # URL/DTMF: линия 0 = авто; иначе то, что выбрали в UI
            pass

        lines.append(f"linekey.{n}.type = {ktype}")
        lines.append(f"linekey.{n}.line = {account}")
        lines.append(f"linekey.{n}.value = {quote_cfg(raw.get('value') or '')}")
        lines.append(f"linekey.{n}.extension = {quote_cfg(raw.get('extension') or '')}")
        lines.append(f"linekey.{n}.label = {quote_cfg(raw.get('label') or '')}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_expkeys_block(exp_keys: list | None) -> str:
    """Блок expansion_module.X.key.Y.* для cfg.

    Пустой список / None → пустая строка (заводская раскладка EXP).
    Ключи: module (1-based), key (1-based), type, account→line, value, extension, label.
    """
    if not exp_keys:
        return ""

    # (module, key) -> raw
    by_mk: dict[tuple[int, int], dict] = {}
    for raw in exp_keys:
        if not isinstance(raw, dict):
            continue
        try:
            module = int(raw.get("module") or 1)
            key = int(raw.get("key") or 0)
        except (TypeError, ValueError):
            continue
        if module < 1 or key < 1:
            continue
        by_mk[(module, key)] = raw

    if not by_mk:
        return ""

    lines: list[str] = []
    for module, key in sorted(by_mk):
        raw = by_mk[(module, key)]
        try:
            ktype = int(raw.get("type") or 0)
        except (TypeError, ValueError):
            ktype = 0
        try:
            account = int(raw.get("account") if raw.get("account") not in (None, "") else 1)
        except (TypeError, ValueError):
            account = 1
        if ktype == 0:
            account = 0

        prefix = f"expansion_module.{module}.key.{key}"
        lines.append(f"{prefix}.type = {ktype}")
        lines.append(f"{prefix}.line = {account}")
        lines.append(f"{prefix}.value = {quote_cfg(raw.get('value') or '')}")
        lines.append(f"{prefix}.extension = {quote_cfg(raw.get('extension') or '')}")
        lines.append(f"{prefix}.label = {quote_cfg(raw.get('label') or '')}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
