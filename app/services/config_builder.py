"""Сборка контекста для Jinja-шаблонов провижининга.

Иерархия файлов Yealink (boot include) уже разделяет global/model/phone,
поэтому здесь словари НЕ сливаются в один flat-dict: иначе параметры
дублировались бы в нескольких cfg и телефон получал конфликты.
"""
import logging
from app.config import settings
from app.models import Phone, Account, PhoneModel, GlobalConfig
from app.security import normalize_mac
from app.phone_accounts import get_account_ids
from app.services.linekeys import render_linekeys_block, render_expkeys_block

logger = logging.getLogger("ntdc.config_builder")


def build_phone_config(db, mac: str) -> dict:
    """Контекст для phone.cfg.j2. ValueError, если MAC нет в БД."""
    mac_clean = normalize_mac(mac) or (mac or "").replace(":", "").replace("-", "").upper()
    logger.debug("Building config for MAC %s", mac_clean)

    phone = db.query(Phone).filter(Phone.mac.ilike(mac_clean)).first()
    if not phone:
        raise ValueError(f"Телефон с MAC {mac} не найден")

    global_cfg = db.query(GlobalConfig).first()
    global_settings = global_cfg.settings if global_cfg and global_cfg.settings else {}

    model = db.query(PhoneModel).filter(PhoneModel.name == phone.model_name).first()
    model_settings = model.default_config if model and model.default_config else {}
    phone_settings = phone.custom_config if phone.custom_config else {}

    final_config = {
        "global": global_settings,
        "model": model_settings,
        "phone": phone_settings,
        "phone_info": {
            "mac": phone.mac,
            "model": phone.model_name,
        },
    }

    # Один IN-запрос вместо N+1
    accounts_data = []
    acc_ids = get_account_ids(db, phone)
    by_id = {}
    if acc_ids:
        rows = db.query(Account).filter(Account.id.in_(acc_ids)).all()
        by_id = {a.id: a for a in rows}
    for idx, acc_id in enumerate(acc_ids, start=1):
        acc = by_id.get(int(acc_id))
        if not acc:
            continue
        accounts_data.append(
            {
                "index": idx,
                "name": acc.name,
                "username": acc.username,
                "password": acc.password,
                "sip_server": acc.sip_server,
                "sip_port": acc.sip_port,
                "transport": acc.transport,
                "display_name": acc.display_name,
            }
        )
    final_config["accounts"] = accounts_data

    # Индивидуальные DSS имеют приоритет над наследством с primary-аккаунта
    dss_keys = []
    if phone.override_dss_keys and phone.custom_dss_keys:
        dss_keys = sorted(phone.custom_dss_keys, key=lambda x: x.get("line", 0))
    elif phone.primary_account_id:
        primary_acc = by_id.get(phone.primary_account_id)
        if primary_acc is None:
            primary_acc = (
                db.query(Account).filter(Account.id == phone.primary_account_id).first()
            )
        if primary_acc and primary_acc.dss_keys:
            dss_keys = sorted(primary_acc.dss_keys, key=lambda x: x.get("line", 0))
    final_config["dss_keys"] = dss_keys

    max_keys = model.max_dss_keys if model and model.max_dss_keys else 27
    final_config["linekeys_block"] = render_linekeys_block(dss_keys, max_keys)

    exp_keys = []
    if getattr(phone, "override_exp_keys", False) and phone.custom_exp_keys:
        exp_keys = list(phone.custom_exp_keys)
    final_config["exp_keys"] = exp_keys
    final_config["expkeys_block"] = render_expkeys_block(exp_keys)

    web_user = (phone.admin_username or settings.PHONE_WEB_USER or "admin").strip() or "admin"
    web_pass = (phone.admin_password or "").strip()
    if not web_pass or web_pass == "admin":
        web_pass = (settings.PHONE_WEB_PASSWORD or "").strip()
    final_config["web_user"] = web_user
    final_config["web_password"] = web_pass if web_pass and web_pass != "admin" else ""

    return final_config


def build_model_config(model_obj, identifier: str) -> dict:
    """Контекст для model.cfg.j2. Неизвестная модель → пустые поля, не 404:
    трубка всё равно запросит $PN.cfg, даже если линейки нет в NTDC.
    """
    config = {
        "model_name": identifier.upper(),
        "model_firmware_url": None,
        "model_802_1x_enable": False,
        "model_802_1x_identity": "",
        "model_802_1x_mode": 0,
        "model_802_1x_md5_password": "",
        "model_802_1x_root_cert_url": "",
        "model_802_1x_client_cert_url": "",
        "model_802_1x_upload_mode": 0,
        "model_default_config": {},
    }
    if model_obj:
        config.update(
            {
                "model_firmware_url": model_obj.firmware_url,
                "model_802_1x_enable": bool(model_obj.ieee802_1x_enable),
                "model_802_1x_identity": model_obj.ieee802_1x_identity,
                "model_802_1x_mode": model_obj.ieee802_1x_mode,
                "model_802_1x_md5_password": model_obj.ieee802_1x_md5_password or "",
                "model_802_1x_root_cert_url": model_obj.ieee802_1x_root_cert_url,
                "model_802_1x_client_cert_url": model_obj.ieee802_1x_client_cert_url,
                "model_802_1x_upload_mode": model_obj.ieee802_1x_upload_mode,
                "model_default_config": model_obj.default_config or {},
            }
        )
    return config
