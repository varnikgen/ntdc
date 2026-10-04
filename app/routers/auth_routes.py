"""Форма входа и выход из админки."""

from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.middleware.auth import (
    authenticate,
    login_user,
    logout_user,
    session_identity,
    throttle,
    _client_ip,
)

router = APIRouter(tags=["auth"])


def _safe_next(next_url: str | None) -> str:
    """Только относительный путь внутри сайта — защита от open redirect."""
    if not next_url:
        return "/"
    next_url = next_url.strip()
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return "/"
    if not next_url.startswith("/"):
        return "/"
    if next_url.startswith("//"):
        return "/"
    if next_url.startswith("/login"):
        return "/"
    return next_url


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    if session_identity(request):
        return RedirectResponse(_safe_next(next), status_code=status.HTTP_303_SEE_OTHER)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": _safe_next(next),
            "error": None,
            "username": "",
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
):
    templates: Jinja2Templates = request.app.state.templates
    next_url = _safe_next(next)
    ip = _client_ip(request)

    if throttle.is_locked(ip):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": next_url,
                "error": "Слишком много неудачных попыток. Подождите минуту.",
                "username": username,
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    identity = authenticate((username or "").strip(), password or "")
    if not identity:
        throttle.record_failure(ip)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": next_url,
                "error": "Неверный логин или пароль",
                "username": username,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    throttle.record_success(ip)
    user, role = identity
    login_user(request, user, role)
    return RedirectResponse(next_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
@router.post("/logout")
async def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
