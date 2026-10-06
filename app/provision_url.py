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


def web_password_lines(global_settings: dict | None = None) -> list[str]:
    """security.user_password = admin:… и user:… (одинаковый ключ, две строки)."""
    data = global_settings or {}
    admin_pw = (data.get("ntdc.phone.admin_password") or settings.PHONE_WEB_PASSWORD or "").strip()
    user_pw = (data.get("ntdc.phone.user_password") or "").strip()
    user_name = (settings.PHONE_WEB_USER or "admin").strip() or "admin"
    lines = []
    if admin_pw and admin_pw != "admin":
        lines.append(f"security.user_password = {quote_cfg(f'{user_name}:{admin_pw}')}")
    if user_pw and user_pw != "user":
        lines.append(f"security.user_password = {quote_cfg(f'user:{user_pw}')}")
    return lines


def boot_file_body() -> str:
    mode = int(settings.BOOT_OVERWRITE_MODE)
    return (
        "#!version:1.0.0.1\n"
        f"overwrite_mode = {mode}\n"
        'include:config "y000000000000.cfg"\n'
        'include:config "$PN.cfg"\n'
        'include:config "$MAC.cfg"\n'
    )
