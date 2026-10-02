"""Глобальные параметры y000000000000.cfg.

PARAM_GROUPS задаёт порядок секций в UI. Ключи вне групп попадают
в блок Custom Parameters.

Boolean: в шаблоне hidden value=0 + checkbox value=1 с тем же name.
FormData отдаёт оба, последнее побеждает — снятая галочка сохраняется как 0.
PASSWORD_PARAMS: пустая строка не перезаписывает секрет в БД.
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
import time
from datetime import datetime, timedelta


from app.database import get_db
from app.models import GlobalConfig
from app.services.audit import log_action, admin_user

router = APIRouter(prefix="/settings", tags=["settings"])

PARAM_LABELS = {
    "static.network.ip_address_mode": "IP Address Mode",
    "static.network.ipv6_enable": "Enable IPv6",
    "static.network.static_dns_enable": "Use Static DNS",
    "static.network.primary_dns": "Primary DNS",
    "static.network.secondary_dns": "Secondary DNS",
    "static.network.vlan.internet_port_enable": "Enable VLAN",
    "static.network.vlan.internet_port_vid": "VLAN ID",
    "static.network.vlan.internet_port_priority": "VLAN Priority (CoS)",
    "ldap.enable": "Enable LDAP",
    "ldap.host": "LDAP Server",
    "ldap.base": "Base DN",
    "ldap.user": "LDAP User",
    "ldap.password": "LDAP Password",
    "ldap.name_attr": "Name Attributes",
    "ldap.numb_attr": "Number Attribute",
    "ldap.name_filter": "Name Filter",
    "ldap.number_filter": "Number Filter",
    "ldap.display_name": "Display Name Format",
    "ldap.call_in_lookup": "Enable Call-In Lookup",
    "ldap.customize_label": "LDAP Label",
    "local_time.time_zone": "Time Zone",
    "local_time.dhcp_time": "Use DHCP Time",
    "local_time.summer_time": "Enable Summer Time",
    "local_time.date_format": "Date Format",
    "local_time.time_zone_name": "Time Zone Name",
    "static.auto_provision.server.url": "Provisioning Server URL",
    "static.auto_provision.power_on": "Auto Provision on Power On",
    "static.auto_provision.repeat.minutes": "Repeat Interval (minutes)",
    "static.auto_provision.custom.protect": "Protect Custom Settings",
    "static.auto_provision.weekly.enable": "Enable Weekly Provisioning",
    "static.auto_provision.username": "Provisioning Username",
    "static.auto_provision.password": "Provisioning Password",
    "features.action_uri_limit_ip": "Action URI Allowed Server IP",
    "features.action_uri.phone.enable": "Enable Phone Action URI",
    "features.action_uri.expansion_module.enable": "Enable Expansion Module Action URI",
    "action_url.enable": "Enable Action URL",
    "action_url.limit_ip": "Action URL Limit IP",
    "action_url.registered": "Registered URL",
    "action_url.unregistered": "Unregistered URL",
    "action_url.register_failed": "Registration Failed URL",
    "action_url.registration_failed": "Registration Failed URL (legacy)",
    "action_url.off_hook": "Off Hook URL",
    "action_url.on_hook": "On Hook URL",
    "action_url.incoming_call": "Incoming Call URL",
    "action_url.outgoing_call": "Outgoing Call URL",
    "action_url.call_established": "Call Established URL",
    "action_url.call_missed": "Call Missed URL",
    "action_url.dnd_on": "DND On URL",
    "action_url.dnd_off": "DND Off URL",
    "action_url.setup_completed": "Setup Completed URL",
    "action_url.setup_complete": "Setup Complete URL (legacy)",
    "features.remote_phonebook.enable": "Enable Remote Phonebook",
    "features.dnd.allow": "Allow DND",
    "features.fwd.allow": "Allow Forward",
    "features.show_action_uri_option": "Show Action URI Option",
    "phone_setting.ring_type": "Ring Tone",
    "voice.handset.spk_vol": "Handset Speaker Volume",
    "voice.ring_vol": "Ring Volume",
    "directory.edit_default_input_method": "Directory Input Method",
    "action_url.show_msgbox": "Show Action URL Message Box",
    "ncdc.phone.admin_password": "Phone admin password",
    "ncdc.phone.user_password": "Phone user password",
}

SELECT_OPTIONS = {
    "static.network.ip_address_mode": {
        "0": "IPv4 Only",
        "1": "IPv6 Only",
        "2": "IPv4 & IPv6",
    },
    "local_time.date_format": {
        "0": "YYYY-MM-DD",
        "1": "DD-MM-YYYY",
        "2": "MM-DD-YYYY",
        "3": "DD/MM/YYYY",
        "4": "MM/DD/YYYY",
        "5": "YYYY/MM/DD",
    },
    "local_time.time_zone": {
        "-12": "UTC-12",
        "-11": "UTC-11",
        "-10": "UTC-10",
        "-9": "UTC-9",
        "-8": "UTC-8 (PST)",
        "-7": "UTC-7 (MST)",
        "-6": "UTC-6 (CST)",
        "-5": "UTC-5 (EST)",
        "-4": "UTC-4",
        "-3": "UTC-3",
        "-2": "UTC-2",
        "-1": "UTC-1",
        "0": "UTC+0 (GMT)",
        "+1": "UTC+1 (CET)",
        "+2": "UTC+2 (EET)",
        "+3": "UTC+3 (MSK)",
        "+4": "UTC+4",
        "+5": "UTC+5",
        "+6": "UTC+6",
        "+7": "UTC+7",
        "+8": "UTC+8",
        "+9": "UTC+9",
        "+10": "UTC+10 (VLAT)",
        "+11": "UTC+11",
        "+12": "UTC+12",
    },
}

PARAM_GROUPS = {
    "Network": [
        "static.network.ip_address_mode",
        "static.network.ipv6_enable",
        "static.network.static_dns_enable",
        "static.network.primary_dns",
        "static.network.secondary_dns",
        "static.network.vlan.internet_port_enable",
        "static.network.vlan.internet_port_vid",
        "static.network.vlan.internet_port_priority",
    ],
    "LDAP": [
        "ldap.enable",
        "ldap.host",
        "ldap.base",
        "ldap.user",
        "ldap.password",
        "ldap.name_attr",
        "ldap.numb_attr",
        "ldap.name_filter",
        "ldap.number_filter",
        "ldap.display_name",
        "ldap.call_in_lookup",
        "ldap.customize_label",
    ],
    "Time & Date": [
        "local_time.time_zone",
        "local_time.dhcp_time",
        "local_time.summer_time",
        "local_time.date_format",
        "local_time.time_zone_name",
    ],
    "Auto Provision": [
        "static.auto_provision.server.url",
        "static.auto_provision.username",
        "static.auto_provision.password",
        "static.auto_provision.power_on",
        "static.auto_provision.repeat.minutes",
        "static.auto_provision.custom.protect",
        "static.auto_provision.weekly.enable",
    ],
    "Phone Web UI": [
        "ncdc.phone.admin_password",
        "ncdc.phone.user_password",
    ],
    "Action URI": [
        "features.action_uri_limit_ip",
        "features.action_uri.phone.enable",
        "features.action_uri.expansion_module.enable",
    ],
    "Action URL Events": [
        "action_url.enable",
        "action_url.limit_ip",
        "action_url.registered",
        "action_url.unregistered",
        "action_url.register_failed",
        "action_url.off_hook",
        "action_url.on_hook",
        "action_url.incoming_call",
        "action_url.outgoing_call",
        "action_url.call_established",
        "action_url.call_missed",
        "action_url.dnd_on",
        "action_url.dnd_off",
        "action_url.setup_completed",
    ],
    "Features": [
        "features.remote_phonebook.enable",
        "features.dnd.allow",
        "features.fwd.allow",
        "features.show_action_uri_option",
        "phone_setting.ring_type",
        "voice.handset.spk_vol",
        "voice.ring_vol",
        "directory.edit_default_input_method",
        "action_url.show_msgbox",
    ],
}

BOOLEAN_PARAMS = {
    "static.network.ipv6_enable",
    "static.network.static_dns_enable",
    "static.network.vlan.internet_port_enable",
    "ldap.enable",
    "ldap.call_in_lookup",
    "local_time.dhcp_time",
    "local_time.summer_time",
    "static.auto_provision.power_on",
    "static.auto_provision.custom.protect",
    "static.auto_provision.weekly.enable",
    "features.action_uri.phone.enable",
    "features.action_uri.expansion_module.enable",
    "features.remote_phonebook.enable",
    "features.dnd.allow",
    "features.fwd.allow",
    "features.show_action_uri_option",
    "action_url.show_msgbox",
    "action_url.enable",
}

INT_PARAMS = {
    "static.network.vlan.internet_port_vid",
    "static.network.vlan.internet_port_priority",
    "static.auto_provision.repeat.minutes",
    "voice.handset.spk_vol",
    "voice.ring_vol",
}

PASSWORD_PARAMS = {
    "ldap.password",
    "static.auto_provision.password",
    "ncdc.phone.admin_password",
    "ncdc.phone.user_password",
}

AUTO_ENROLL_UNTIL = None


def normalize_value(param: str, value: str):
    """Yealink ждёт 0/1 и int, форма всегда шлёт строки."""
    if param in BOOLEAN_PARAMS:
        return 1 if str(value) in ("1", "on", "true", "True") else 0
    if param in INT_PARAMS:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    return value


def _grouped(settings: dict) -> dict:
    grouped = {}
    for group_name, params in PARAM_GROUPS.items():
        group_data = []
        for param in params:
            value = settings.get(param, "")
            group_data.append(
                {
                    "key": param,
                    "label": PARAM_LABELS.get(param, param),
                    "value": value,
                    "type": (
                        "password"
                        if param in PASSWORD_PARAMS
                        else "select"
                        if param in SELECT_OPTIONS
                        else "boolean"
                        if param in BOOLEAN_PARAMS
                        else "text"
                    ),
                    "options": SELECT_OPTIONS.get(param, {}),
                }
            )
        grouped[group_name] = group_data
    return grouped


@router.get("/global")
async def global_config(request: Request, db: Session = Depends(get_db)):
    global_cfg = db.query(GlobalConfig).first()
    settings_map = global_cfg.settings if global_cfg and global_cfg.settings else {}
    grouped_settings = _grouped(settings_map)

    known_params = set()
    for params in PARAM_GROUPS.values():
        known_params.update(params)

    custom_params = []
    for key, value in settings_map.items():
        if key not in known_params:
            custom_params.append(
                {"key": key, "label": key, "value": value, "type": "text", "options": {}}
            )

    return request.app.state.templates.TemplateResponse(
        "settings/global.html",
        {
            "request": request,
            "grouped_settings": grouped_settings,
            "custom_params": custom_params,
        },
    )


@router.post("/global")
async def update_global_config(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    global_cfg = db.query(GlobalConfig).first()
    if not global_cfg:
        global_cfg = GlobalConfig(settings={})
        db.add(global_cfg)

    cfg_settings = dict(global_cfg.settings) if global_cfg.settings else {}
    changed_params = []

    for key, value in form.items():
        if not key.startswith("param_"):
            continue
        param_name = key.replace("param_", "", 1)
        if param_name in PASSWORD_PARAMS and (value is None or str(value).strip() == ""):
            continue  # пустое поле пароля = оставить как было
        normalized = normalize_value(param_name, value)
        old_value = cfg_settings.get(param_name)
        if old_value != normalized:
            display_new = "********" if param_name in PASSWORD_PARAMS else normalized
            display_old = "********" if param_name in PASSWORD_PARAMS else old_value
            changed_params.append(f"{param_name}: {display_old} → {display_new}")
        cfg_settings[param_name] = normalized

    for key, value in form.items():
        if key.startswith("delete_"):
            param_name = key.replace("delete_", "", 1)
            if param_name in cfg_settings:
                changed_params.append(f"{param_name}: {cfg_settings[param_name]} → [deleted]")
                del cfg_settings[param_name]

    global_cfg.settings = cfg_settings  # перепривязка dict — иначе JSON-колонка не увидит diff
    db.commit()
    db.refresh(global_cfg)
    log_action(
        db,
        "UPDATE_GLOBAL_CONFIG",
        "GlobalConfig",
        global_cfg.id,
        admin_user(request),
        f"Updated global config: {', '.join(changed_params) if changed_params else 'no changes'}",
    )
    return {"status": "success", "message": "Глобальные настройки успешно сохранены"}

@router.post("/auto-enroll/enable")
async def enable_auto_enroll(request: Request, db: Session = Depends(get_db), minutes: int = 30):
    """Временно включить AUTO_ENROLL на указанное количество минут"""
    global AUTO_ENROLL_UNTIL
    AUTO_ENROLL_UNTIL = datetime.utcnow() + timedelta(minutes=minutes)
    
    log_action(db, "ENABLE_AUTO_ENROLL", "Settings", 0, admin_user(request), 
               f"Auto-enroll enabled for {minutes} minutes (until {AUTO_ENROLL_UNTIL})")
    
    return {"status": "success", "message": f"Auto-enroll enabled until {AUTO_ENROLL_UNTIL}"}

@router.post("/auto-enroll/disable")
async def disable_auto_enroll(request: Request, db: Session = Depends(get_db)):
    """Отключить AUTO_ENROLL"""
    global AUTO_ENROLL_UNTIL
    AUTO_ENROLL_UNTIL = None
    
    log_action(db, "DISABLE_AUTO_ENROLL", "Settings", 0, admin_user(request), "Auto-enroll disabled")
    
    return {"status": "success", "message": "Auto-enroll disabled"}

@router.get("/auto-enroll/status")
async def auto_enroll_status():
    """Проверить статус AUTO_ENROLL"""
    global AUTO_ENROLL_UNTIL
    
    if AUTO_ENROLL_UNTIL and datetime.utcnow() < AUTO_ENROLL_UNTIL:
        remaining = (AUTO_ENROLL_UNTIL - datetime.utcnow()).seconds // 60
        return {"enabled": True, "until": AUTO_ENROLL_UNTIL.isoformat(), "remaining_minutes": remaining}
    else:
        AUTO_ENROLL_UNTIL = None  # Сброс если время вышло
        return {"enabled": False}

@router.post("/import-configs")
async def import_configs(request: Request, db: Session = Depends(get_db)):
    """Пакетная загрузка экспортированных cfg-файлов Yealink."""
    from app.services.cfg_import import import_cfg_file
    from app.services.audit import log_action, admin_user

    form = await request.form()
    uploads = form.getlist("files")
    if not uploads:
        raise HTTPException(status_code=400, detail="Файлы не загружены")

    report = []
    for up in uploads:
        data = await up.read()
        text = data.decode("utf-8", errors="replace")
        report.append(import_cfg_file(db, up.filename or "unknown.cfg", text))

    ok = sum(1 for r in report if r["ok"])
    log_action(db, "IMPORT_CONFIGS", "Settings", 0, admin_user(request),
               f"Imported {ok}/{len(report)} config files")
    return {"status": "success", "imported": ok, "total": len(report), "report": report}
