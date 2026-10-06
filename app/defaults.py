"""Стартовые значения y000000000000.cfg.

$mac в Action URL — переменная Yealink: трубка подставит свой MAC сама.
Токен обязателен, иначе любой в сети сможет менять IP/статус устройств.
"""

from app.config import settings


def action_url(event: str) -> str:
    """Собирает Action URL с токеном, MAC-плейсхолдером и именем события."""
    token = settings.ACTION_URI_TOKEN
    return (
        f"{settings.base_url}/actions/"
        f"?token={token}&mac=$mac&ip=$ip&event={event}"
    )


def default_global_settings() -> dict:
    cfg = {
        "static.auto_provision.server.url": f"{settings.base_url}/provision/",
        "static.auto_provision.power_on": 1,
        "static.auto_provision.repeat.minutes": 60,  # не 1: иначе тысячи трубок долбят сервер
        "static.network.ip_address_mode": 0,         # 0=IPv4 only; 1=IPv6 only ломает сеть
        "static.network.ipv6_enable": 0,
        "local_time.time_zone": "+10",
        "local_time.dhcp_time": 1,
        "ldap.enable": 0,
        # any = принимать Action URI (AutoP) с любого IP; пустая строка на части
        # прошивок = никому, и тогда /servlet?key=AutoP с NTDC не доходит.
        "features.action_uri_limit_ip": "any",
        "action_url.enable": 1,
        "action_url.registered": action_url("registered"),
        "action_url.unregistered": action_url("unregistered"),
        "action_url.register_failed": action_url("registration_failed"),
        "action_url.dnd_on": action_url("dnd_on"),
        "action_url.dnd_off": action_url("dnd_off"),
        "action_url.setup_completed": action_url("setup_complete"),
        "features.action_uri.phone.enable": 1,
    }
    if settings.PROVISION_AUTH_ENABLED and settings.PROVISION_USER and settings.PROVISION_PASS:
        cfg["static.auto_provision.username"] = settings.PROVISION_USER
        cfg["static.auto_provision.password"] = settings.PROVISION_PASS
    if (settings.PHONE_WEB_PASSWORD or "").strip() and settings.PHONE_WEB_PASSWORD != "admin":
        cfg["ntdc.phone.admin_password"] = settings.PHONE_WEB_PASSWORD.strip()
    return cfg


def seed_global_config(db) -> None:
    """Первый старт — полная запись. Повторный — дописывает только пустые ключи."""
    from app.models import GlobalConfig

    row = db.query(GlobalConfig).first()
    if row is None:
        db.add(GlobalConfig(settings=default_global_settings()))
        db.commit()
        return

    current = dict(row.settings or {})
    changed = False
    # Старые имена ключей Yealink, которые трубка игнорирует
    renames = {
        "action_url.registration_failed": "action_url.register_failed",
        "action_url.setup_complete": "action_url.setup_completed",
    }
    for old, new in renames.items():
        if old in current and new not in current:
            current[new] = current.pop(old)
            changed = True
        elif old in current and new in current:
            current.pop(old)
            changed = True
    for key, value in list(current.items()):
        if key.startswith("action_url.") and isinstance(value, str) and "mac=$mac" in value and "ip=$ip" not in value:
            current[key] = value.replace("mac=$mac", "mac=$mac&ip=$ip")
            changed = True
    for key, value in default_global_settings().items():
        if key not in current or current[key] in (None, ""):
            current[key] = value
            changed = True
    if changed:
        row.settings = current  # нужна перепривязка dict, иначе SQLAlchemy JSON не увидит diff
        db.commit()
