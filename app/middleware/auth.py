"""Авторизация админки: сессия (cookie) + опционально HTTP Basic.

1) Session cookie ncdc_session (логин через /login)
2) HTTP Basic — для скриптов/API (если передан заголовок)
3) Fallback-учётка из .env (NCDC_ADMIN_*)

Провижининг (/provision) — отдельно через provision_authorized().
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import quote

from fastapi import Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

from app.config import settings
from app.security import constant_time_equals, LoginThrottle, verify_password

logger = logging.getLogger("ncdc.auth")

ADMIN_EXCLUDED_PREFIXES = (
    "/provision",
    "/health",
    "/actions",
    "/favicon.ico",
    "/static",
    "/login",
    "/logout",
)

# Полный доступ — только admin.
# operator / viewer — только устройства и аккаунты (+ дашборд).
ADMIN_ONLY_PREFIXES = ("/users",)

OPERATOR_ALLOWED_PREFIXES = (
    "/",          # dashboard (точное совпадение ниже)
    "/phones",
    "/accounts",
)

SESSION_USER_KEY = "admin_user"
SESSION_ROLE_KEY = "admin_role"

throttle = LoginThrottle(
    max_failures=settings.LOGIN_MAX_FAILURES,
    lockout_seconds=settings.LOGIN_LOCKOUT_SECONDS,
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return True
    # браузерный переход без явного Accept JSON
    if request.method == "GET" and "application/json" not in accept:
        return True
    return False


def _unauthorized(request: Request, detail: str = "Unauthorized"):
    if _wants_html(request):
        next_url = request.url.path
        if request.url.query:
            next_url += "?" + request.url.query
        return RedirectResponse(
            url=f"/login?next={quote(next_url, safe='')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return PlainTextResponse(
        detail,
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": 'Basic realm="NCDC Admin Panel"'},
    )


def _forbidden(detail: str = "Forbidden") -> PlainTextResponse:
    return PlainTextResponse(detail, status_code=status.HTTP_403_FORBIDDEN)


def _decode_basic(auth_header: str) -> tuple[str, str] | None:
    try:
        scheme, credentials = auth_header.split(None, 1)
        if scheme.lower() != "basic":
            return None
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def provision_authorized(request: Request) -> bool:
    if not settings.PROVISION_AUTH_ENABLED:
        return True
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return False
    parsed = _decode_basic(auth_header)
    if not parsed:
        return False
    username, password = parsed
    return constant_time_equals(username, settings.PROVISION_USER) and constant_time_equals(
        password, settings.PROVISION_PASS
    )


def authenticate(username: str, password: str) -> tuple[str, str] | None:
    """Проверяет логин/пароль. Возвращает (username, role) или None."""
    try:
        from app.database import SessionLocal
        from app.models import AdminUser

        db = SessionLocal()
        try:
            user = db.query(AdminUser).filter(AdminUser.username == username).first()
            if user and user.is_active and verify_password(password, user.password_hash):
                return user.username, user.role
        finally:
            db.close()
    except Exception as exc:
        logger.debug("DB auth lookup failed: %s", exc)

    user_ok = constant_time_equals(username, settings.NCDC_ADMIN_USER)
    pass_ok = constant_time_equals(password, settings.NCDC_ADMIN_PASS)
    if user_ok and pass_ok and settings.NCDC_ADMIN_PASS:
        return settings.NCDC_ADMIN_USER, "admin"

    return None


def login_user(request: Request, username: str, role: str) -> None:
    request.session[SESSION_USER_KEY] = username
    request.session[SESSION_ROLE_KEY] = role


def logout_user(request: Request) -> None:
    request.session.clear()


def session_identity(request: Request) -> tuple[str, str] | None:
    # SessionMiddleware должен стоять снаружи auth; защищаемся на всякий случай
    if "session" not in request.scope:
        return None
    user = request.session.get(SESSION_USER_KEY)
    role = request.session.get(SESSION_ROLE_KEY)
    if user and role:
        return str(user), str(role)
    return None


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if any(path.startswith(prefix) for prefix in ADMIN_EXCLUDED_PREFIXES):
        return await call_next(request)

    ip = _client_ip(request)
    if throttle.is_locked(ip):
        return JSONResponse(
            {"detail": "Too many failed login attempts. Try again later."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    identity = session_identity(request)

    # Опционально: HTTP Basic для API/скриптов
    if not identity:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parsed = _decode_basic(auth_header)
            if parsed:
                username, password = parsed
                identity = authenticate(username, password)
                if identity:
                    throttle.record_success(ip)
                else:
                    throttle.record_failure(ip)
                    logger.warning("Failed Basic login from %s user=%s", ip, username)
                    return _unauthorized(request, "Incorrect username or password")

    if not identity:
        return _unauthorized(request)

    auth_user, role = identity
    request.state.admin_user = auth_user
    request.state.admin_role = role

    # --- Role ACL ---
    if role == "admin":
        return await call_next(request)

    # admin-only areas
    if any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
        return _forbidden("Admin role required")

    # operator / viewer: only phones, accounts, dashboard
    if role in ("operator", "viewer"):
        allowed = False
        if path == "/" or path == "":
            allowed = True
        elif any(path == pfx or path.startswith(pfx + "/") for pfx in OPERATOR_ALLOWED_PREFIXES if pfx != "/"):
            allowed = True
        if not allowed:
            return _forbidden("Access denied for role '%s'" % role)

    if role == "viewer" and request.method.upper() not in ("GET", "HEAD", "OPTIONS"):
        return _forbidden("Viewer role is read-only")

    return await call_next(request)


# обратная совместимость имени
basic_auth_middleware = auth_middleware
