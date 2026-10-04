"""Точка входа FastAPI: lifespan, middleware, роутеры, дашборд."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db, run_migrations
from app.defaults import seed_global_config
from app.middleware.auth import auth_middleware
from app.middleware.csrf import csrf_middleware
from app.middleware.i18n import I18nMiddleware
from app.models import Phone
from app.routers import (
    accounts,
    actions,
    audit as audit_router,
    dashboard as dashboard_router,
    models as models_router,
    phones,
    provisioning,
    settings as settings_router,
    users as users_router,
)
from app.routers import auth_routes

from app.services.audit_cleanup import background_tasks

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ncdc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Не поднимаемся с пустым/слитым паролем — лучше явный crash, чем открытая админка
    errors = settings.validate_security()
    if errors:
        for err in errors:
            logger.error("Startup config error: %s", err)
        raise RuntimeError("Refusing to start: " + " | ".join(errors))

    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    run_migrations()
    from app.phone_accounts import migrate_json_to_table
    from app.database import SessionLocal as _SL
    _db = _SL()
    try:
        n = migrate_json_to_table(_db)
        if n:
            import logging
            logging.getLogger("ncdc").info("Migrated account_ids for %s phones", n)
    finally:
        _db.close()
    db = SessionLocal()
    try:
        seed_global_config(db)
    finally:
        db.close()

    task = asyncio.create_task(background_tasks())
    logger.info("%s v%s started", settings.APP_NAME, settings.APP_VERSION)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Yealink Auto-Provisioning Service",
    lifespan=lifespan,
)

# HTML-шаблоны админки (с autoescape). Cfg-файлы рендерятся через app.provision_templates.
templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# add_middleware вставляет в начало стека: последний вызов = самый внешний слой.
# Нужно: Session (outer) → Auth → CSRF → app
# поэтому SessionMiddleware регистрируем ПОСЛЕДНИМ.
app.middleware("http")(csrf_middleware)
app.middleware("http")(auth_middleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="ncdc_session",
    max_age=60 * 60 * 24 * 7,  # 7 дней
    same_site="lax",
    https_only=False,  # True только если весь доступ строго по HTTPS
)
app.add_middleware(I18nMiddleware)

app.include_router(provisioning.router)
app.include_router(actions.router)
app.include_router(phones.router)
app.include_router(accounts.router)
app.include_router(settings_router.router)
app.include_router(models_router.router)
app.include_router(audit_router.router)
app.include_router(dashboard_router.router)
app.include_router(users_router.router)
app.include_router(auth_routes.router)


@app.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total = db.query(Phone).count()
    online = db.query(Phone).filter(Phone.status == "online").count()
    dnd = db.query(Phone).filter(Phone.status == "dnd").count()
    offline = db.query(Phone).filter(Phone.status == "offline").count()
    unregistered = db.query(Phone).filter(Phone.status == "unregistered").count()
    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": {
                "total": total,
                "online": online,
                "dnd": dnd,
                "offline": offline,
                "unregistered": unregistered,
            },
        },
    )


@app.get("/health")
async def health_check():
    """Открытый эндпоинт для compose healthcheck. Без секретов."""
    return {"status": "healthy", "version": settings.APP_VERSION}
