"""AutoP push: GET /servlet?key=AutoP на веб-UI трубки.

Сначала HTTPS, при ошибке HTTP — часть T4x держит UI только на 80.
Не требуем status=online: иначе Unregistered навсегда блокирует применение cfg.
"""
import logging
from sqlalchemy.orm import Session
import httpx

from app.config import settings
from app.models import Phone

logger = logging.getLogger("ntdc.push_service")


async def trigger_phone_autop(db: Session, phone_id: int) -> tuple[bool, str]:
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        return False, "телефон не найден"
    if not phone.ip_address:
        return False, "нет IP — трубка ещё не стучалась (Action URL / provision)"

    username = phone.admin_username or "admin"
    password = phone.admin_password or "admin"

    urls = [
        f"https://{phone.ip_address}/servlet?key=AutoP",
        f"http://{phone.ip_address}/servlet?key=AutoP",
    ]
    last_error = ""
    for url in urls:
        try:
            async with httpx.AsyncClient(
                timeout=settings.AUTOP_TIMEOUT,
                verify=settings.AUTOP_VERIFY_SSL,
                auth=(username, password),
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                if response.status_code in (200, 204):
                    logger.info("AutoP sent to %s (%s) via %s", phone.ip_address, phone.mac, url)
                    return True, f"отправлен на {phone.ip_address}"
                last_error = f"HTTP {response.status_code} {url}"
                logger.warning("AutoP to %s returned %s", url, response.status_code)
        except Exception as exc:
            last_error = f"{url}: {exc}"
            logger.warning("AutoP error %s", last_error)

    return False, last_error or "телефон не ответил на AutoP"
