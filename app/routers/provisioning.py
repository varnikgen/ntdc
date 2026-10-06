"""Выдача Yealink cfg.

.boot без Basic и без лишних ключей — иначе трубка не качает includes.
PROVISION_BOOTSTRAP=true: cfg тоже без Basic (заводской сброс).
false: cfg только с PROVISION_USER/PASS (учётки тогда из DHCP option 66).
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
import logging

from app.config import settings
from app.database import get_db
from app.middleware.auth import provision_authorized
from app.models import Phone, PhoneModel, GlobalConfig
from app.provision_templates import jinja_env
from app.provision_url import boot_file_body
from app.routers.settings import auto_enroll_active
from app.security import MAC_RE, normalize_mac, detect_model_from_ua
from app.phone_ip import pick_phone_ip, reported_phone_ip
from app.services.config_builder import build_phone_config, build_model_config
from app.services.audit import log_action

router = APIRouter(prefix="/provision", tags=["provisioning"])
logger = logging.getLogger("ntdc.provision")


def _require_cfg_auth(request: Request) -> None:
    if provision_authorized(request):
        return
    if settings.PROVISION_BOOTSTRAP:
        return
    raise HTTPException(
        status_code=401,
        detail="Provisioning credentials required",
        headers={"WWW-Authenticate": 'Basic realm="NTDC Provisioning"'},
    )


def _touch_phone(db, phone: Phone, request: Request) -> None:
    chosen = pick_phone_ip(reported_phone_ip(request), None, phone.ip_address)
    phone.ip_address = chosen
    phone.last_seen = datetime.utcnow()
    db.commit()


def _render(name: str, context: dict) -> Response:
    template = jinja_env.get_template(name)
    return Response(content=template.render(**context), media_type="text/plain")


@router.get("/y000000000000.boot")
@router.get("/{mac}.boot")
async def get_boot_file(mac: str = "y000000000000"):
    return Response(content=boot_file_body(), media_type="text/plain")


@router.get("/y000000000000.cfg")
async def get_global_config(request: Request, db: Session = Depends(get_db)):
    _require_cfg_auth(request)
    global_cfg = db.query(GlobalConfig).first()
    cfg_settings = global_cfg.settings if global_cfg and global_cfg.settings else {}
    return _render("y000000000000.cfg.j2", {"config": {"global": cfg_settings}})


@router.get("/{identifier}.cfg")
async def get_config(identifier: str, request: Request, db: Session = Depends(get_db)):
    """12 hex → phone cfg; иначе считаем identifier именем модели ($PN)."""
    _require_cfg_auth(request)

    if MAC_RE.match(identifier):
        mac = normalize_mac(identifier)
        phone = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
        
        if not phone:
            # Проверяем AUTO_ENROLL (из .env ИЛИ временное включение)
            auto_enroll_enabled = settings.AUTO_ENROLL or auto_enroll_active()
            
            if auto_enroll_enabled:
                user_agent = request.headers.get("user-agent", "")
                model_name = detect_model_from_ua(user_agent)
                phone = Phone(
                    mac=mac,
                    status="unregistered",
                    model_name=model_name,
                )
                db.add(phone)
                db.commit()
                log_action(
                    db, "AUTO_ENROLL", "Phone", phone.id, "provision",
                    f"Enrolled {mac} with model {model_name or 'unknown'}",
                )
                logger.info("Auto-enrolled phone %s with model %s", mac, model_name)
            else:
                raise HTTPException(status_code=404, detail="Unknown MAC")
        
        _touch_phone(db, phone, request)

        if not phone.model_name:
            model_name = detect_model_from_ua(request.headers.get("user-agent", ""))
            if model_name:
                phone.model_name = model_name
                db.commit()
                logger.info("Detected model %s for %s from User-Agent", phone.model_name, phone.mac)
        
        try:
            config_data = build_phone_config(db, mac)
        except ValueError:
            raise HTTPException(status_code=404, detail="Unknown MAC")
        
        return _render("phone.cfg.j2", {"config": config_data})

    model_obj = db.query(PhoneModel).filter(PhoneModel.name == identifier.upper()).first()
    config = build_model_config(model_obj, identifier)
    return _render("model.cfg.j2", {"config": config})
