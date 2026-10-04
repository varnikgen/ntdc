"""Язык UI: ?lang=ru|en → cookie, иначе cookie, иначе ru."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from app.i18n import COOKIE_NAME, DEFAULT_LANG, Translator, normalize_lang


class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        lang = None
        qp = request.query_params.get("lang")
        if qp:
            lang = normalize_lang(qp)
        if not lang:
            lang = normalize_lang(request.cookies.get(COOKIE_NAME))
        request.state.lang = lang or DEFAULT_LANG
        request.state.t = Translator(request.state.lang)

        response = await call_next(request)

        # если переключили через ?lang= — зафиксировать cookie
        if qp and normalize_lang(qp) == request.state.lang:
            response.set_cookie(
                COOKIE_NAME,
                request.state.lang,
                max_age=60 * 60 * 24 * 365,
                httponly=False,
                samesite="lax",
                path="/",
            )
        return response
