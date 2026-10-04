"""SIP-аккаунты.

account_ids на телефоне — JSON-список без FK, поэтому при DELETE аккаунта
обходим все трубки и вычищаем id вручную (_detach_account_from_phones).
Пустой password на update = оставить прежний.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.pagination import parse_page_args, paginate, page_url, ALLOWED_PER_PAGE
from app.formutil import parse_json_list
from app.models import Account, Phone
from app.services.audit import log_action, admin_user

router = APIRouter(prefix="/accounts", tags=["accounts"])




def _detach_account_from_phones(db: Session, account_id: int) -> None:
    from app.phone_accounts import detach_account
    detach_account(db, account_id)



@router.get("/")
async def list_accounts(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 25,
    q: str = "",
):
    page, per_page = parse_page_args(page, per_page)
    q = (q or "").strip()

    query = db.query(Account).order_by(Account.name)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Account.name.ilike(like),
                Account.username.ilike(like),
                Account.sip_server.ilike(like),
                Account.display_name.ilike(like),
            )
        )

    pg = paginate(query, page, per_page)
    return request.app.state.templates.TemplateResponse(
        "accounts/list.html",
        {
            "request": request,
            "accounts": pg["rows"],
            "pagination": pg,
            "q": q,
            "per_page_options": ALLOWED_PER_PAGE,
            "page_url": lambda p: page_url("/accounts/", p, per_page, q),
        },
    )


@router.get("/new")
async def new_account(request: Request):
    return request.app.state.templates.TemplateResponse(
        "accounts/edit.html", {"request": request, "account": None, "dss_keys": []}
    )


@router.post("/")
async def create_account(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    password = form.get("password") or ""
    if not password:
        raise HTTPException(status_code=400, detail="Пароль обязателен")

    account = Account(
        name=form.get("name"),
        sip_server=form.get("sip_server"),
        sip_port=int(form.get("sip_port") or 5060),
        transport=form.get("transport") or "udp",
        username=form.get("username"),
        password=password,
        display_name=form.get("display_name"),
        dss_keys=parse_json_list(form.get("dss_keys")),
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Аккаунт с таким username уже существует")
    db.refresh(account)
    log_action(db, "CREATE_ACCOUNT", "Account", account.id, admin_user(request), f"Created account {account.name}")
    return {"status": "success", "message": f"Аккаунт {account.name} создан", "redirect": "/accounts"}


@router.get("/{account_id}/edit")
async def edit_account(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return request.app.state.templates.TemplateResponse(
        "accounts/edit.html",
        {"request": request, "account": account, "dss_keys": account.dss_keys or []},
    )


@router.post("/{account_id}/update")
async def update_account(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    form = await request.form()
    account.name = form.get("name")
    account.sip_server = form.get("sip_server")
    account.sip_port = int(form.get("sip_port") or 5060)
    account.transport = form.get("transport") or "udp"
    account.username = form.get("username")
    account.display_name = form.get("display_name")
    new_password = form.get("password")
    if new_password:
        account.password = new_password  # пустое = не менять, пароль не светится в value=
    account.dss_keys = parse_json_list(form.get("dss_keys"))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Аккаунт с таким username уже существует")
    db.refresh(account)
    log_action(db, "UPDATE_ACCOUNT", "Account", account.id, admin_user(request), f"Updated account {account.name}")
    return {"status": "success", "message": f"Аккаунт {account.name} обновлен", "redirect": "/accounts"}


@router.post("/{account_id}/delete")
async def delete_account(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    account_name = account.name
    _detach_account_from_phones(db, account_id)
    db.delete(account)
    db.commit()
    log_action(db, "DELETE_ACCOUNT", "Account", account_id, admin_user(request), f"Deleted account {account_name}")
    return {"status": "success", "message": f"Аккаунт {account_name} удален", "redirect": "/accounts"}
