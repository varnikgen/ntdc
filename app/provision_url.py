"""URL провижининга и минимальный .boot.

.boot у Yealink — не cfg: только overwrite_mode и include:config.
Любой static.* / security.* / user:pass@url в boot — трубка 108.x
перестаёт читать includes и каждую минуту долбит только {mac}.boot.
"""
from urllib.parse import quote, urlparse, urlunparse

from app.config import settings
from app.security import quote_cfg


def provision_http_url(filename: str = "", with_auth: bool = False) -> str:
    parsed = urlparse(settings.base_url)
    host = parsed.hostname or "localhost"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    if with_auth and settings.PROVISION_AUTH_ENABLED and settings.PROVISION_USER:
        user = quote(settings.PROVISION_USER, safe="")
        password = quote(settings.PROVISION_PASS, safe="")
        netloc = f"{user}:{password}@{netloc}"
    path = "/provision/" + filename.lstrip("/")
    return urlunparse((parsed.scheme or "https", netloc, path, "", "", ""))


def resolve_phone_web_passwords(global_settings: dict | None = None) -> tuple[str, str, str]:
    """(admin_user, admin_password, user_password) для веб-UI трубки.

    Пустой / admin → не считаем заданным (Yealink всё равно потребует смену).
    """
    data = global_settings or {}
    admin_user = (settings.PHONE_WEB_USER or "admin").strip() or "admin"
    admin_pw = (
        data.get("ncdc.phone.admin_password")
        or settings.PHONE_WEB_PASSWORD
        or ""
    ).strip()
    user_pw = (data.get("ncdc.phone.user_password") or "").strip()
    if admin_pw == "admin":
        admin_pw = ""
    if user_pw == "user":
        user_pw = ""
    return admin_user, admin_pw, user_pw


def web_password_lines(global_settings: dict | None = None) -> list[str]:
    """Строки cfg для пароля веб-UI.

    Используем static.security.user_password — при auto-provision применяется
    надёжнее, чем security.* без static (важно после factory reset).
    security.password_use_default.enable = 0 отключает экран «смените пароль».
    """
    admin_user, admin_pw, user_pw = resolve_phone_web_passwords(global_settings)
    lines: list[str] = []
    if admin_pw:
        lines.append(f"static.security.user_name.admin = {quote_cfg(admin_user)}")
        lines.append(f"static.security.user_password = {quote_cfg(f'{admin_user}:{admin_pw}')}")
        lines.append(f"security.user_password = {quote_cfg(f'{admin_user}:{admin_pw}')}")
    if user_pw:
        lines.append("static.security.user_name.user = user")
        lines.append(f"static.security.user_password = {quote_cfg(f'user:{user_pw}')}")
        lines.append(f"security.user_password = {quote_cfg(f'user:{user_pw}')}")
    if admin_pw or user_pw:
        lines.append("security.password_use_default.enable = 0")
    return lines


def boot_file_body() -> str:
    mode = int(settings.BOOT_OVERWRITE_MODE)
    nl = "\n"
    return (
        "#!version:1.0.0.1" + nl
        + f"overwrite_mode = {mode}" + nl
        + 'include:config "y000000000000.cfg"' + nl
        + 'include:config "$PN.cfg"' + nl
        + 'include:config "$MAC.cfg"' + nl
    )
