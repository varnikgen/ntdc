"""CSRF double-submit cookie.

Не читаем request.form() здесь: это вычерпало бы body и сломало роутеры.
Все POST админки идут через fetch()/HTMX и шлют заголовок X-CSRF-Token
(см. monkey-patch fetch в base.html).

/provision и /actions исключены — телефоны заголовок не посылают.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

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


async def csrf_middleware(request: Request, call_next):
    path = request.url.path
    if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return await call_next(request)

    cookie = request.cookies.get(CSRF_COOKIE)

    if request.method not in SAFE_METHODS:
        header = request.headers.get(CSRF_HEADER, "")
        if not cookie or not header or not constant_time_equals(cookie, header):
            return JSONResponse(
                {"detail": "CSRF token missing or invalid"},
                status_code=status.HTTP_403_FORBIDDEN,
            )

    response = await call_next(request)
    if not cookie:
        response.set_cookie(
            CSRF_COOKIE,
            new_token(24),
            httponly=False,  # JS должен прочитать cookie, чтобы поставить заголовок
            samesite="lax",  # strict ломает заход по IP после редиректа с имени
            secure=request.url.scheme == "https",
            path="/",
        )
    return response
