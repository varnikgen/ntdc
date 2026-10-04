"""Два контура авторизации.

Админка — HTTP Basic:
  1) пользователи из таблицы admin_users (если есть);
  2) fallback на NCDC_ADMIN_USER / NCDC_ADMIN_PASS из .env (роль admin).

Провижининг (/provision) — отдельно через provision_authorized().
/actions, /health, /static исключены.
"""

from fastapi import Request, status
from fastapi.responses import PlainTextResponse, JSONResponse
import base64
import logging

from app.config import settings
from app.security import constant_time_equals, LoginThrottle, verify_password

logger = logging.getLogger("ncdc.auth")

ADMIN_EXCLUDED_PREFIXES = (
    "/provision",
    "/health",
    "/actions",
    "/favicon.ico",
    "/static",
)

# Маршруты только для role=admin
ADMIN_ONLY_PREFIXES = (
    "/users",
)

throttle = LoginThrottle(
    max_failures=settings.LOGIN_MAX_FAILURES,
    lockout_seconds=settings.LOGIN_LOCKOUT_SECONDS,
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _unauthorized(detail: str = "Unauthorized") -> PlainTextResponse:
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


def _authenticate(username: str, password: str) -> tuple[str, str] | None:
    """Возвращает (username, role) или None."""
    # 1. DB users
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

    # 2. Env bootstrap admin
    user_ok = constant_time_equals(username, settings.NCDC_ADMIN_USER)
    pass_ok = constant_time_equals(password, settings.NCDC_ADMIN_PASS)
    if user_ok and pass_ok and settings.NCDC_ADMIN_PASS:
        return settings.NCDC_ADMIN_USER, "admin"

    return None


async def basic_auth_middleware(request: Request, call_next):
    path = request.url.path

    if any(path.startswith(prefix) for prefix in ADMIN_EXCLUDED_PREFIXES):
        return await call_next(request)

    ip = _client_ip(request)
    if throttle.is_locked(ip):
        return JSONResponse(
            {"detail": "Too many failed login attempts. Try again later."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return _unauthorized()

    parsed = _decode_basic(auth_header)
    if not parsed:
        return PlainTextResponse("Invalid authorization header", status_code=400)

    username, password = parsed
    identity = _authenticate(username, password)
    if not identity:
        throttle.record_failure(ip)
        logger.warning("Failed admin login from %s user=%s", ip, username)
        return _unauthorized("Incorrect username or password")

    throttle.record_success(ip)
    auth_user, role = identity
    request.state.admin_user = auth_user
    request.state.admin_role = role

    # Role gate for /users
    if any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
        if role != "admin":
            return _forbidden("Admin role required")

    # Viewer: only GET/HEAD
    if role == "viewer" and request.method.upper() not in ("GET", "HEAD", "OPTIONS"):
        return _forbidden("Viewer role is read-only")

    return await call_next(request)
