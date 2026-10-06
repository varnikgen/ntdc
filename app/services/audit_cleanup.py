"""Фоновый цикл (раз в минуту): чистка аудита и перевод молчащих трубок в offline.

Сессия своя, не из Depends: задача живёт всё время процесса.
При ошибке — rollback + close в finally, иначе SQLite остаётся залоченной.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog, Phone

logger = logging.getLogger("ntdc.maintenance")

# Ограничение параллельных опросов веб-UI трубок
_PROBE_CONCURRENCY = 10


async def check_phone_availability(
    client: httpx.AsyncClient, phone_ip: str
) -> bool:
    """HTTPS до веб-UI. 401/403 тоже «жив» — интерфейс отвечает, просто закрыт паролем."""
    try:
        response = await client.get(f"https://{phone_ip}/")
        return response.status_code in (200, 401, 403)
    except Exception:
        return False


async def background_tasks():
    logger.info(
        "Background tasks started (audit %s days, offline timeout %s min)",
        settings.AUDIT_RETENTION_DAYS,
        settings.OFFLINE_TIMEOUT_MINUTES,
    )

    timeout = httpx.Timeout(3.0, connect=2.0)
    limits = httpx.Limits(max_connections=_PROBE_CONCURRENCY, max_keepalive_connections=5)

    async with httpx.AsyncClient(
        timeout=timeout,
        verify=settings.AUTOP_VERIFY_SSL,
        limits=limits,
    ) as client:
        sem = asyncio.Semaphore(_PROBE_CONCURRENCY)

        async def probe(ip: str) -> bool:
            async with sem:
                return await check_phone_availability(client, ip)

        while True:
            await asyncio.sleep(60)
            db = SessionLocal()
            try:
                cutoff_audit = datetime.utcnow() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
                deleted_logs = (
                    db.query(AuditLog).filter(AuditLog.timestamp < cutoff_audit).delete()
                )
                if deleted_logs:
                    logger.info("Purged %s audit rows", deleted_logs)

                cutoff_phone = datetime.utcnow() - timedelta(
                    minutes=settings.OFFLINE_TIMEOUT_MINUTES
                )
                offline_candidates = (
                    db.query(Phone)
                    .filter(
                        Phone.status.in_(["online", "dnd"]),
                        Phone.last_seen < cutoff_phone,
                        Phone.ip_address.isnot(None),
                    )
                    .all()
                )

                dirty = bool(deleted_logs)
                if offline_candidates:
                    results = await asyncio.gather(
                        *[probe(p.ip_address) for p in offline_candidates],
                        return_exceptions=True,
                    )
                    now = datetime.utcnow()
                    for phone, result in zip(offline_candidates, results):
                        is_available = result is True
                        if is_available:
                            phone.last_seen = now
                            logger.debug(
                                "Phone %s still reachable, last_seen refreshed", phone.mac
                            )
                        else:
                            phone.status = "offline"
                            logger.warning("Phone %s marked offline", phone.mac)
                        dirty = True

                if dirty:
                    db.commit()
            except Exception:
                db.rollback()
                logger.exception("Background task failed")
            finally:
                db.close()
