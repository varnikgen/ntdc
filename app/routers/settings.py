"""Глобальные параметры y000000000000.cfg.

PARAM_GROUPS задаёт порядок секций в UI. Ключи вне групп попадают
в блок Custom Parameters.

Boolean: в шаблоне hidden value=0 + checkbox value=1 с тем же name.
FormData отдаёт оба, последнее побеждает — снятая галочка сохраняется как 0.
PASSWORD_PARAMS: пустая строка не перезаписывает секрет в БД.
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
import time
from datetime import datetime, timedelta


from app.database import get_db
from app.models import GlobalConfig, PhoneModel
from app.services.audit import log_action, admin_user
from app.settings_schema import (
    PARAM_LABELS,
    SELECT_OPTIONS,
    PARAM_GROUPS,
    BOOLEAN_PARAMS,
    INT_PARAMS,
    PASSWORD_PARAMS,
)

router = APIRouter(prefix="/settings", tags=["settings"])

AUTO_ENROLL_UNTIL = None


def auto_enroll_active() -> bool:
    """Живая проверка: включён ли временный auto-enroll прямо сейчас."""
    global AUTO_ENROLL_UNTIL
    if AUTO_ENROLL_UNTIL and datetime.utcnow() < AUTO_ENROLL_UNTIL:
        return True
    AUTO_ENROLL_UNTIL = None
    return False

def normalize_value(param: str, value: str):
    """Yealink ждёт 0/1 и int, форма всегда шлёт строки."""
    if param in BOOLEAN_PARAMS:
        return 1 if str(value) in ("1", "on", "true", "True") else 0
    if param in INT_PARAMS:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    return value


def _grouped(settings: dict) -> dict:
    grouped = {}
    for group_name, params in PARAM_GROUPS.items():
        group_data = []
        for param in params:
            value = settings.get(param, "")
            group_data.append(
                {
                    "key": param,
                    "label": PARAM_LABELS.get(param, param),
                    "value": value,
                    "type": (
                        "password"
                        if param in PASSWORD_PARAMS
                        else "select"
                        if param in SELECT_OPTIONS
                        else "boolean"
                        if param in BOOLEAN_PARAMS
                        else "text"
                    ),
                    "options": SELECT_OPTIONS.get(param, {}),
                }
            )
        grouped[group_name] = group_data
    return grouped


@router.get("/global")
async def global_config(request: Request, db: Session = Depends(get_db)):
    global_cfg = db.query(GlobalConfig).first()
    settings_map = global_cfg.settings if global_cfg and global_cfg.settings else {}
    grouped_settings = _grouped(settings_map)

    known_params = set()
    for params in PARAM_GROUPS.values():
        known_params.update(params)

    custom_params = []
    for key, value in settings_map.items():
        if key not in known_params:
            custom_params.append(
                {"key": key, "label": key, "value": value, "type": "text", "options": {}}
            )

    return request.app.state.templates.TemplateResponse(
        "settings/global.html",
        {
            "request": request,
            "grouped_settings": grouped_settings,
            "custom_params": custom_params,
            "models": db.query(PhoneModel).order_by(PhoneModel.name).all(),  # <-- ДОБАВИТЬ
        },
    )


@router.post("/global")
async def update_global_config(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    global_cfg = db.query(GlobalConfig).first()
    if not global_cfg:
        global_cfg = GlobalConfig(settings={})
        db.add(global_cfg)

    cfg_settings = dict(global_cfg.settings) if global_cfg.settings else {}
    changed_params = []

    for key, value in form.items():
        if not key.startswith("param_"):
            continue
        param_name = key.replace("param_", "", 1)
        if param_name in PASSWORD_PARAMS and (value is None or str(value).strip() == ""):
            continue  # пустое поле пароля = оставить как было
        normalized = normalize_value(param_name, value)
        old_value = cfg_settings.get(param_name)
        if old_value != normalized:
            display_new = "********" if param_name in PASSWORD_PARAMS else normalized
            display_old = "********" if param_name in PASSWORD_PARAMS else old_value
            changed_params.append(f"{param_name}: {display_old} → {display_new}")
        cfg_settings[param_name] = normalized

    for key, value in form.items():
        if key.startswith("delete_"):
            param_name = key.replace("delete_", "", 1)
            if param_name in cfg_settings:
                changed_params.append(f"{param_name}: {cfg_settings[param_name]} → [deleted]")
                del cfg_settings[param_name]

    global_cfg.settings = cfg_settings  # перепривязка dict — иначе JSON-колонка не увидит diff
    db.commit()
    db.refresh(global_cfg)
    log_action(
        db,
        "UPDATE_GLOBAL_CONFIG",
        "GlobalConfig",
        global_cfg.id,
        admin_user(request),
        f"Updated global config: {', '.join(changed_params) if changed_params else 'no changes'}",
    )
    return {"status": "success", "message": "Глобальные настройки успешно сохранены"}

@router.post("/auto-enroll/enable")
async def enable_auto_enroll(request: Request, db: Session = Depends(get_db), minutes: int = 30):
    """Временно включить AUTO_ENROLL на указанное количество минут"""
    global AUTO_ENROLL_UNTIL
    AUTO_ENROLL_UNTIL = datetime.utcnow() + timedelta(minutes=minutes)
    
    log_action(db, "ENABLE_AUTO_ENROLL", "Settings", 0, admin_user(request), 
               f"Auto-enroll enabled for {minutes} minutes (until {AUTO_ENROLL_UNTIL})")
    
    return {"status": "success", "message": f"Auto-enroll enabled until {AUTO_ENROLL_UNTIL}"}

@router.post("/auto-enroll/disable")
async def disable_auto_enroll(request: Request, db: Session = Depends(get_db)):
    """Отключить AUTO_ENROLL"""
    global AUTO_ENROLL_UNTIL
    AUTO_ENROLL_UNTIL = None
    
    log_action(db, "DISABLE_AUTO_ENROLL", "Settings", 0, admin_user(request), "Auto-enroll disabled")
    
    return {"status": "success", "message": "Auto-enroll disabled"}

@router.get("/auto-enroll/status")
async def auto_enroll_status():
    """Проверить статус AUTO_ENROLL"""
    global AUTO_ENROLL_UNTIL
    
    if AUTO_ENROLL_UNTIL and datetime.utcnow() < AUTO_ENROLL_UNTIL:
        remaining = (AUTO_ENROLL_UNTIL - datetime.utcnow()).seconds // 60
        return {"enabled": True, "until": AUTO_ENROLL_UNTIL.isoformat(), "remaining_minutes": remaining}
    else:
        AUTO_ENROLL_UNTIL = None  # Сброс если время вышло
        return {"enabled": False}

@router.post("/import-configs")
async def import_configs(request: Request, db: Session = Depends(get_db)):
    """Пакетная загрузка экспортированных cfg-файлов Yealink."""
    from app.services.cfg_import import import_batch
    from app.services.audit import log_action, admin_user

    form = await request.form()
    uploads = form.getlist("files")
    if not uploads:
        raise HTTPException(status_code=400, detail="Файлы не загружены")

    model_name = form.get("model") or None
    promote = form.get("promote") == "1"

    files = []
    for up in uploads:
        data = await up.read()
        files.append((up.filename or "unknown.cfg", data.decode("utf-8", errors="replace")))

    result = import_batch(db, files, model_name, promote)

    log_action(db, "IMPORT_CONFIGS", "Settings", 0, admin_user(request),
               f"Imported {result['imported']}/{result['total']}, "
               f"promoted to global: {len(result['promoted'])}")
    return result
