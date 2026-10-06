"""Action URI: трубка сама стучится при register / DND / unregistered.

Защита — query-параметр token (не Basic): Yealink подставляет его в URL
из глобального cfg. Без токена любой мог бы подменить IP устройства
и затем отправить AutoP на чужой адрес.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.config import settings
from app.database import get_db
from app.models import Phone
from app.security import extract_mac, constant_time_equals, detect_model_from_ua
from app.phone_ip import pick_phone_ip, reported_phone_ip, request_src_ip
from app.services.audit import log_action

router = APIRouter(prefix="/actions", tags=["actions"])
logger = logging.getLogger("ntdc.actions")

DND_ON_EVENTS = {"dnd_on", "dndon", "DNDOn"}
DND_OFF_EVENTS = {"dnd_off", "dndoff", "DNDOff"}


@router.get("/")
@router.post("/")
async def handle_action_url(request: Request, db: Session = Depends(get_db)):
    """Обновляет last_seen/IP/статус. При AUTO_ENROLL создаёт Phone."""
    token = request.query_params.get("token", "")
    if not settings.ACTION_URI_TOKEN or not constant_time_equals(token, settings.ACTION_URI_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid action token")

    src_ip = request_src_ip(request)
    reported_ip = reported_phone_ip(request)
    user_agent = request.headers.get("user-agent", "")
    mac = extract_mac(user_agent, request.query_params.get("mac", ""))

    if not mac:
        logger.warning("Action URL ignored: MAC not found (UA=%s src=%s)", user_agent, src_ip)
        return {"status": "ignored", "reason": "Unknown MAC"}

    phone = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
    created = False
    if not phone:
        if not settings.AUTO_ENROLL:
            logger.warning("Action URL for unknown MAC %s", mac)
            return {"status": "ignored", "reason": "Phone not found"}
        model_name = detect_model_from_ua(user_agent)
        phone = Phone(mac=mac, status="unregistered", model_name=model_name)
        db.add(phone)
        created = True
    elif not phone.model_name:
        model_name = detect_model_from_ua(user_agent)
        if model_name:
            phone.model_name = model_name

    chosen = pick_phone_ip(reported_ip, None, phone.ip_address)
    phone.ip_address = chosen
    phone.last_seen = datetime.utcnow()

    event = request.query_params.get("event", "")
    event_norm = event.lower().replace(" ", "_").replace("-", "_")
    if event_norm in {"registered", "setup_complete", "setup_completed", "reged", "register"}:
        phone.status = "online"
    elif event_norm in {"unregistered", "registration_failed", "register_failed"}:
        phone.status = "unregistered"
    elif event in DND_ON_EVENTS or event_norm in DND_ON_EVENTS:
        phone.status = "dnd"
    elif event in DND_OFF_EVENTS or event_norm in DND_OFF_EVENTS:
        phone.status = "online"

    db.commit()
    if created:
        log_action(db, "AUTO_ENROLL", "Phone", phone.id, "action-uri", f"Enrolled {mac} from {chosen or src_ip}")
    logger.info(
        "Action URL %s MAC=%s ip=%s reported=%s src=%s event=%s",
        "created" if created else "updated",
        mac,
        chosen,
        reported_ip,
        src_ip,
        event,
    )
    return {"status": "success", "mac": mac, "created": created, "ip": chosen}
