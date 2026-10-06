"""Синхронная пометка offline.

Основной цикл — audit_cleanup.background_tasks (ещё пингует HTTPS).
Этот модуль — для ручного вызова из скриптов и тестов.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Phone
from app.config import settings
import logging

logger = logging.getLogger("ntdc.status_checker")


def update_offline_phones(db: Session, timeout_minutes: int | None = None):
    timeout = timeout_minutes if timeout_minutes is not None else settings.OFFLINE_TIMEOUT_MINUTES
    cutoff_time = datetime.utcnow() - timedelta(minutes=timeout)
    result = (
        db.query(Phone)
        .filter(Phone.status.in_(["online", "dnd"]), Phone.last_seen < cutoff_time)
        .update({"status": "offline"})
    )
    db.commit()
    if result:
        logger.info("Marked %s phones offline", result)
    return result
