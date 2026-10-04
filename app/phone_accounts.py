"""Работа с линиями SIP телефона (таблица phone_accounts).

JSON phones.account_ids оставлен для совместимости и синхронизируется при записи.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Phone, PhoneAccount, Account


def get_account_ids(db: Session, phone: Phone) -> list[int]:
    if phone.id is None:
        raw = phone.account_ids if isinstance(phone.account_ids, list) else []
        return [int(x) for x in raw if x is not None]
    rows = (
        db.query(PhoneAccount)
        .filter(PhoneAccount.phone_id == phone.id)
        .order_by(PhoneAccount.line_no)
        .all()
    )
    if rows:
        return [r.account_id for r in rows]
    raw = phone.account_ids if isinstance(phone.account_ids, list) else []
    return [int(x) for x in raw if x is not None]


def set_account_ids(db: Session, phone: Phone, account_ids: list[int]) -> None:
    """Полностью заменяет набор линий; синхронизирует JSON account_ids."""
    ids = [int(x) for x in account_ids if x is not None]
    if phone.id is not None:
        db.query(PhoneAccount).filter(PhoneAccount.phone_id == phone.id).delete()
        for line_no, acc_id in enumerate(ids, start=1):
            db.add(PhoneAccount(phone_id=phone.id, line_no=line_no, account_id=acc_id))
    phone.account_ids = ids


def detach_account(db: Session, account_id: int) -> int:
    """Удаляет account со всех линий. Возвращает число изменённых телефонов."""
    account_id = int(account_id)
    phone_ids: set[int] = set()

    for (pid,) in db.query(PhoneAccount.phone_id).filter(
        PhoneAccount.account_id == account_id
    ).all():
        phone_ids.add(pid)

    for (pid,) in db.query(Phone.id).filter(Phone.primary_account_id == account_id).all():
        phone_ids.add(pid)

    # legacy JSON (ещё не смигрированные)
    for phone in db.query(Phone).all():
        raw = phone.account_ids if isinstance(phone.account_ids, list) else []
        try:
            if account_id in [int(x) for x in raw if x is not None]:
                phone_ids.add(phone.id)
        except (TypeError, ValueError):
            continue

    if not phone_ids:
        return 0

    db.query(PhoneAccount).filter(PhoneAccount.account_id == account_id).delete()

    changed = 0
    phones = db.query(Phone).filter(Phone.id.in_(phone_ids)).all()
    for phone in phones:
        ids = get_account_ids(db, phone)
        # get_account_ids may still return the deleted id from JSON only
        ids = [i for i in ids if i != account_id]
        set_account_ids(db, phone, ids)
        if phone.primary_account_id == account_id:
            phone.primary_account_id = ids[0] if ids else None
        changed += 1
    return changed


def migrate_json_to_table(db: Session) -> int:
    """Одноразовая миграция account_ids JSON → phone_accounts."""
    phones = db.query(Phone).all()
    migrated = 0
    for phone in phones:
        existing = (
            db.query(PhoneAccount).filter(PhoneAccount.phone_id == phone.id).count()
        )
        if existing:
            continue
        raw = phone.account_ids if isinstance(phone.account_ids, list) else []
        ids = []
        for x in raw:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                continue
        if not ids:
            continue
        for line_no, acc_id in enumerate(ids, start=1):
            if not db.query(Account.id).filter(Account.id == acc_id).first():
                continue
            db.add(
                PhoneAccount(phone_id=phone.id, line_no=line_no, account_id=acc_id)
            )
        migrated += 1
    if migrated:
        db.commit()
    return migrated
