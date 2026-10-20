"""CSRF double-submit cookie.

Не читаем request.form() здесь: это вычерпало бы body и сломало роутеры.
Админка шлёт заголовок X-CSRF-Token (fetch patch + meta csrf-token в base.html).

/provision и /actions исключены — телефоны заголовок не посылают.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.security import constant_time_equals, new_token

CSRF_COOKIE = "ntdc_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
EXCLUDED_PREFIXES = (
    "/provision",
    "/health",
    "/actions",
    "/static",
    "/favicon.ico",
    "/login",
    "/logout",
)


def _cookie_secure() -> bool:
    """Secure по публичному URL (за reverse-proxy request.scheme часто http)."""
    base = (getattr(settings, "PUBLIC_BASE_URL", None) or settings.base_url or "").lower()
    return base.startswith("https://")


async def csrf_middleware(request: Request, call_next):
    path = request.url.path
    if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return await call_next(request)

    cookie = request.cookies.get(CSRF_COOKIE)
    # Один токен на запрос: из cookie или новый (отдадим в meta + Set-Cookie)
    token = cookie if cookie else new_token(24)
    request.state.csrf_token = token

    if request.method not in SAFE_METHODS:
        header = request.headers.get(CSRF_HEADER, "") or ""
        if not cookie or not header or not constant_time_equals(cookie, header):
            return JSONResponse(
                {"detail": "CSRF token missing or invalid"},
                status_code=status.HTTP_403_FORBIDDEN,
            )

    response = await call_next(request)

    # Всегда выставляем cookie (обновляем, если не было)
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,  # JS читает для заголовка
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
        max_age=60 * 60 * 24 * 7,
    )
    return response
