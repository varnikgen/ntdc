"""CRUD устройств.

Формы шлют JSON-строки (custom_config, custom_dss_keys, account_ids),
а не набор custom_* полей: иначе имя параметра путалось с его значением.

GET /phones/{id}/dss-keys — HTMX-partial при переключении Override DSS Keys.
Пустой admin_password при update = оставить прежний (не затирать полем-заглушкой).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, case
from sqlalchemy.exc import IntegrityError
import logging

from app.database import get_db
from app.pagination import parse_page_args, paginate, page_url, ALLOWED_PER_PAGE
from app.formutil import parse_json_field
from app.models import Phone, Account, PhoneModel
from app.security import normalize_mac
from app.phone_ip import is_phone_ip, is_container_ip
from app.services.push_service import trigger_phone_autop
from app.services.audit import log_action, admin_user

router = APIRouter(prefix="/phones", tags=["phones"])
logger = logging.getLogger("ncdc.phones")


@router.get("/")
async def list_phones(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 25,
    q: str = "",
):
    page, per_page = parse_page_args(page, per_page)
    q = (q or "").strip()

    # один проход по таблице вместо 4× COUNT
    total, online, dnd, offline = db.query(
        func.count(Phone.id),
        func.coalesce(func.sum(case((Phone.status == "online", 1), else_=0)), 0),
        func.coalesce(func.sum(case((Phone.status == "dnd", 1), else_=0)), 0),
        func.coalesce(
            func.sum(case((Phone.status.in_(("offline", "unregistered")), 1), else_=0)),
            0,
        ),
    ).one()
    stats = {
        "total": int(total or 0),
        "online": int(online or 0),
        "dnd": int(dnd or 0),
        "offline": int(offline or 0),
    }

    query = db.query(Phone).order_by(Phone.last_seen.desc(), Phone.mac)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Phone.mac.ilike(like),
                Phone.model_name.ilike(like),
                Phone.ip_address.ilike(like),
                Phone.status.ilike(like),
            )
        )

    pg = paginate(query, page, per_page)
    return request.app.state.templates.TemplateResponse(
        "phones/list.html",
        {
            "request": request,
            "phones": pg["rows"],
            "stats": stats,
            "pagination": pg,
            "q": q,
            "per_page_options": ALLOWED_PER_PAGE,
            "page_url": lambda p: page_url("/phones/", p, per_page, q),
        },
    )


@router.get("/new")
async def new_phone(request: Request, db: Session = Depends(get_db)):
    # Тот же шаблон, что и edit: phone=None переключает форму в режим создания
    return request.app.state.templates.TemplateResponse(
        "phones/edit.html",
        {
            "request": request,
            "phone": None,
            "accounts": db.query(Account).order_by(Account.name).all(),
            "models": db.query(PhoneModel).order_by(PhoneModel.name).all(),
            "current_dss": [],
            "inherit_from_account": False,
            "phone_account_count": 0,
        },
    )


@router.post("/")
async def create_phone(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    mac = normalize_mac(form.get("mac", ""))
    if not mac:
        raise HTTPException(status_code=400, detail="MAC-адрес должен содержать 12 hex-символов")

    phone = Phone(
        mac=mac,
        model_name=form.get("model_name") or None,
        admin_username=form.get("admin_username") or "admin",
        admin_password=form.get("admin_password") or "admin",
        ip_address=form.get("ip_address") or None,
        status="offline",
        account_ids=[],
        custom_config={},
    )
    primary_id = form.get("primary_account_id")
    phone.primary_account_id = int(primary_id) if primary_id else None
    acc_ids_str = form.get("account_ids", "")
    ids = [int(x.strip()) for x in acc_ids_str.split(",") if x.strip()] if acc_ids_str else []
    # Primary всегда линия 1, даже если JS не положил его в account_ids
    if phone.primary_account_id and phone.primary_account_id not in ids:
        ids = [phone.primary_account_id] + ids
    phone.account_ids = ids

    db.add(phone)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Телефон с MAC {mac} уже существует")
    db.refresh(phone)
    log_action(db, "CREATE_PHONE", "Phone", phone.id, admin_user(request), f"Created phone {phone.mac}")
    return {"status": "success", "message": f"Телефон {phone.mac} создан", "redirect": "/phones"}


@router.get("/{phone_id}/edit")
async def edit_phone(request: Request, phone_id: int, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Телефон не найден")

    accounts = db.query(Account).all()
    models = db.query(PhoneModel).all()

    # Что показать в таблице DSS: свои клавиши либо наследство primary-аккаунта
    if phone.override_dss_keys and phone.custom_dss_keys:
        current_dss = sorted(phone.custom_dss_keys, key=lambda x: x.get("line", 0))
        inherit_from_account = False
    elif phone.primary_account_id:
        primary_acc = db.query(Account).filter(Account.id == phone.primary_account_id).first()
        raw_dss = primary_acc.dss_keys if primary_acc else []
        current_dss = sorted(raw_dss, key=lambda x: x.get("line", 0))
        inherit_from_account = True
    else:
        current_dss = []
        inherit_from_account = False

    phone_account_count = len(phone.account_ids) if phone.account_ids else 0
    return request.app.state.templates.TemplateResponse(
        "phones/edit.html",
        {
            "request": request,
            "phone": phone,
            "accounts": accounts,
            "models": models,
            "current_dss": current_dss,
            "inherit_from_account": inherit_from_account,
            "phone_account_count": phone_account_count,
        },
    )


@router.post("/{phone_id}/update")
async def update_phone(request: Request, phone_id: int, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Телефон не найден")

    form = await request.form()
    phone.model_name = form.get("model_name") or None
    phone.override_dss_keys = form.get("override_dss_keys") in ("on", "1", "true")

    ip = (form.get("ip_address") or "").strip()
    if ip:
        if not is_phone_ip(ip):
            raise HTTPException(
                status_code=400,
                detail="Это адрес контейнерной сети (10.89.x / docker), не LAN трубки. Укажите 10.30.17.68 или оставьте пустым.",
            )
        phone.ip_address = ip
    elif phone.ip_address and is_container_ip(phone.ip_address):
        phone.ip_address = None

    if form.get("admin_username"):
        phone.admin_username = form.get("admin_username")
    new_admin_pass = form.get("admin_password")
    if new_admin_pass:
        phone.admin_password = new_admin_pass  # пустое поле формы сюда не попадает

    acc_ids_str = form.get("account_ids", "")
    phone.account_ids = [int(x.strip()) for x in acc_ids_str.split(",") if x.strip()] if acc_ids_str else []

    primary_id = form.get("primary_account_id")
    phone.primary_account_id = int(primary_id) if primary_id else None

    if phone.override_dss_keys:
        phone.custom_dss_keys = parse_json_field(form.get("custom_dss_keys"), [])
    else:
        phone.custom_dss_keys = None  # снова наследуем от аккаунта

    phone.custom_config = parse_json_field(form.get("custom_config"), {})

    db.commit()
    db.refresh(phone)
    log_action(db, "UPDATE_PHONE", "Phone", phone.id, admin_user(request), f"Updated phone {phone.mac}")

    pushed = False
    autop_detail = ""
    if phone.ip_address:
        pushed, autop_detail = await trigger_phone_autop(db, phone.id)
    else:
        autop_detail = "нет IP — AutoP некуда отправить"

    message = f"Телефон {phone.mac} успешно обновлен"
    if pushed:
        message += f". AutoP {autop_detail}."
    else:
        message += f". AutoP не отправлен: {autop_detail}."

    return {
        "status": "success",
        "message": message,
        "autop": pushed,
        "autop_detail": autop_detail,
        "redirect": f"/phones/{phone_id}/edit",
    }


@router.post("/{phone_id}/autop")
async def push_autop(request: Request, phone_id: int, db: Session = Depends(get_db)):
    """Ручной AutoP, не зависит от статуса online/unregistered."""
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Телефон не найден")
    pushed, detail = await trigger_phone_autop(db, phone.id)
    log_action(db, "PUSH_AUTOP", "Phone", phone.id, admin_user(request), detail)
    return {"status": "success" if pushed else "error", "message": detail, "autop": pushed}


@router.post("/{phone_id}/delete")
async def delete_phone(request: Request, phone_id: int, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Телефон не найден")
    mac = phone.mac
    db.delete(phone)
    db.commit()
    log_action(db, "DELETE_PHONE", "Phone", phone_id, admin_user(request), f"Deleted phone {mac}")
    return {"status": "success", "message": f"Телефон {mac} удален", "redirect": "/phones"}


@router.get("/{phone_id}/dss-keys")
async def get_dss_keys(request: Request, phone_id: int, db: Session = Depends(get_db)):
    """Фрагмент таблицы для HTMX hx-target=#dssKeysContainer."""
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")

    if phone.primary_account_id:
        primary_acc = db.query(Account).filter(Account.id == phone.primary_account_id).first()
        raw_dss = primary_acc.dss_keys if primary_acc else []
        current_dss = sorted(raw_dss, key=lambda x: x.get("line", 0))
    else:
        current_dss = []

    phone_account_count = len(phone.account_ids) if phone.account_ids else 0
    return request.app.state.templates.TemplateResponse(
        "phones/_dss_keys_table.html",
        {
            "request": request,
            "current_dss": current_dss,
            "phone_account_count": phone_account_count,
        },
    )
