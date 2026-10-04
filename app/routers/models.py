"""Модели аппаратов (T46U, T31G, …).

name совпадает с Yealink $PN и именем файла $PN.cfg — после создания
его нельзя переименовать (readonly в UI, в update name не трогаем).
Удаление блокируется, пока модель назначена хотя бы одному телефону.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.formutil import parse_json_dict
from app.models import PhoneModel, Phone
from app.services.audit import log_action, admin_user

router = APIRouter(prefix="/models", tags=["models"])


def _parse_default_config(raw, fallback=None):
    """Невалидный/пустой JSON на update → fallback (не затираем старое)."""
    if raw is None or raw == "":
        return fallback
    data = parse_json_dict(raw)
    # parse_json_dict на битом JSON вернёт {} — отличаем от явного {}
    if data == {} and raw not in ("{}", "{ }"):
        # если строка не пустая и не "{}", считаем ошибкой парса
        import json as _json
        try:
            parsed = _json.loads(raw)
            return parsed if isinstance(parsed, dict) else fallback
        except Exception:
            return fallback
    return data if isinstance(data, dict) else fallback


@router.get("/")
async def list_models(request: Request, db: Session = Depends(get_db)):
    models = db.query(PhoneModel).order_by(PhoneModel.name).all()
    return request.app.state.templates.TemplateResponse(
        "models/list.html", {"request": request, "models": models}
    )


@router.get("/new")
async def new_model(request: Request):
    return request.app.state.templates.TemplateResponse(
        "models/edit.html", {"request": request, "model": None, "default_config_json": "{}"}
    )


@router.post("/")
async def create_model(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    name = (form.get("name") or "").strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="Имя модели обязательно")

    model = PhoneModel(
        name=name,
        max_accounts=int(form.get("max_accounts") or 12),
        max_dss_keys=int(form.get("max_dss_keys") or 40),
        firmware_url=form.get("firmware_url") or "",
        ieee802_1x_enable=form.get("ieee802_1x_enable") in ("on", "1", "true"),
        ieee802_1x_identity=form.get("ieee802_1x_identity") or "",
        ieee802_1x_mode=int(form.get("ieee802_1x_mode") or 0),
        ieee802_1x_md5_password=form.get("ieee802_1x_md5_password") or "",
        ieee802_1x_root_cert_url=form.get("ieee802_1x_root_cert_url") or "",
        ieee802_1x_client_cert_url=form.get("ieee802_1x_client_cert_url") or "",
        ieee802_1x_upload_mode=int(form.get("ieee802_1x_upload_mode") or 0),
        default_config=_parse_default_config(form.get("default_config"), fallback={}) or {},
    )
    db.add(model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Модель {name} уже существует")
    db.refresh(model)
    log_action(db, "CREATE_MODEL", "PhoneModel", model.id, admin_user(request), f"Created model {model.name}")
    return {"status": "success", "message": f"Модель {model.name} создана", "redirect": "/models"}


@router.get("/{model_id}/edit")
async def edit_model(request: Request, model_id: int, db: Session = Depends(get_db)):
    model = db.query(PhoneModel).filter(PhoneModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    default_config_json = json.dumps(model.default_config, indent=2) if model.default_config else "{}"
    return request.app.state.templates.TemplateResponse(
        "models/edit.html",
        {"request": request, "model": model, "default_config_json": default_config_json},
    )


@router.post("/{model_id}/update")
async def update_model(request: Request, model_id: int, db: Session = Depends(get_db)):
    model = db.query(PhoneModel).filter(PhoneModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не найдена")

    form = await request.form()
    # name не обновляем: на него ссылается Phone.model_name и $PN.cfg
    model.max_accounts = int(form.get("max_accounts") or 12)
    model.max_dss_keys = int(form.get("max_dss_keys") or 40)
    model.firmware_url = form.get("firmware_url") or ""
    model.ieee802_1x_enable = form.get("ieee802_1x_enable") in ("on", "1", "true")
    model.ieee802_1x_identity = form.get("ieee802_1x_identity") or ""
    model.ieee802_1x_mode = int(form.get("ieee802_1x_mode") or 0)
    md5 = form.get("ieee802_1x_md5_password")
    if md5:
        model.ieee802_1x_md5_password = md5
    model.ieee802_1x_root_cert_url = form.get("ieee802_1x_root_cert_url") or ""
    model.ieee802_1x_client_cert_url = form.get("ieee802_1x_client_cert_url") or ""
    model.ieee802_1x_upload_mode = int(form.get("ieee802_1x_upload_mode") or 0)
    parsed = _parse_default_config(form.get("default_config"), fallback=None)
    if parsed is not None:
        model.default_config = parsed

    db.commit()
    db.refresh(model)
    log_action(db, "UPDATE_MODEL", "PhoneModel", model.id, admin_user(request), f"Updated model {model.name}")
    return {"status": "success", "message": f"Модель {model.name} обновлена", "redirect": "/models"}


@router.post("/{model_id}/delete")
async def delete_model(request: Request, model_id: int, db: Session = Depends(get_db)):
    model = db.query(PhoneModel).filter(PhoneModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    in_use = db.query(Phone).filter(Phone.model_name == model.name).count()
    if in_use:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить модель {model.name}: она назначена {in_use} телефонам",
        )
    model_name = model.name
    db.delete(model)
    db.commit()
    log_action(db, "DELETE_MODEL", "PhoneModel", model_id, admin_user(request), f"Deleted model {model_name}")
    return {"status": "success", "message": f"Модель {model_name} удалена", "redirect": "/models"}
