"""Схема UI Global Config: подписи, группы, типы полей.

Вынесено из routers/settings.py.
"""
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
    "ntdc.phone.admin_password": "Phone admin password",
    "ntdc.phone.user_password": "Phone user password",
}

SELECT_OPTIONS = {
    "static.network.ip_address_mode": {
        "0": "IPv4 Only",
        "1": "IPv6 Only",
        "2": "IPv4 & IPv6",
    },
    "local_time.date_format": {
        "0": "WWW MMM DD",
        "1": "DD-MMM-YY",
        "2": "YYYY-MM-DD",
        "3": "DD/MM/YYYY",
        "4": "MM/DD/YY",
        "5": "DD MMM YYYY",
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
        "ntdc.phone.admin_password",
        "ntdc.phone.user_password",
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
    "ntdc.phone.admin_password",
    "ntdc.phone.user_password",
}


# --- i18n labels (technical key stays English under the field) ---

PARAM_LABELS_RU = {
    'action_url.call_established': 'URL: разговор установлен',
    'action_url.call_missed': 'URL: пропущенный вызов',
    'action_url.dnd_off': 'URL: DND выкл',
    'action_url.dnd_on': 'URL: DND вкл',
    'action_url.enable': 'Включить Action URL',
    'action_url.incoming_call': 'URL: входящий вызов',
    'action_url.limit_ip': 'Ограничение IP для Action URL',
    'action_url.off_hook': 'URL: снята трубка',
    'action_url.on_hook': 'URL: положена трубка',
    'action_url.outgoing_call': 'URL: исходящий вызов',
    'action_url.register_failed': 'URL: ошибка регистрации',
    'action_url.registered': 'URL: зарегистрирован',
    'action_url.registration_failed': 'URL: ошибка регистрации (legacy)',
    'action_url.setup_complete': 'URL: настройка завершена (legacy)',
    'action_url.setup_completed': 'URL: настройка завершена',
    'action_url.show_msgbox': 'Показывать сообщение Action URL',
    'action_url.unregistered': 'URL: не зарегистрирован',
    'directory.edit_default_input_method': 'Метод ввода в каталоге',
    'directory.search_default_input_method': 'Метод ввода поиска в каталоге',
    'features.action_uri.expansion_module.enable': 'Action URI модуля расширения',
    'features.action_uri.phone.enable': 'Action URI телефона',
    'features.action_uri_limit_ip': 'Разрешённые IP для Action URI',
    'features.config_dsskey_length': 'Длина подписи DSS-клавиш',
    'features.dnd.allow': 'Разрешить DND',
    'features.fwd.allow': 'Разрешить переадресацию',
    'features.remote_phonebook.enable': 'Удалённая телефонная книга',
    'features.show_action_uri_option': 'Показывать Action URI в меню',
    'ldap.base': 'Base DN',
    'ldap.call_in_lookup': 'Поиск при входящем вызове',
    'ldap.customize_label': 'Подпись LDAP',
    'ldap.display_name': 'Формат отображаемого имени',
    'ldap.enable': 'Включить LDAP',
    'ldap.host': 'Сервер LDAP',
    'ldap.name_attr': 'Атрибуты имени',
    'ldap.name_filter': 'Фильтр по имени',
    'ldap.numb_attr': 'Атрибут номера',
    'ldap.number_filter': 'Фильтр по номеру',
    'ldap.password': 'Пароль LDAP',
    'ldap.user': 'Пользователь LDAP',
    'local_time.date_format': 'Формат даты',
    'local_time.dhcp_time': 'Время по DHCP',
    'local_time.summer_time': 'Летнее время',
    'local_time.time_zone': 'Часовой пояс',
    'local_time.time_zone_name': 'Имя часового пояса',
    'ntdc.phone.admin_password': 'Пароль admin веб-UI телефона',
    'ntdc.phone.user_password': 'Пароль user веб-UI телефона',
    'phone_setting.backgrounds': 'Фоны экрана',
    'phone_setting.custom_headset_mode_status': 'Режим гарнитуры',
    'phone_setting.mute_power_led_flash_enable': 'Мигание LED при Mute',
    'phone_setting.page_tip': 'Подсказки на экране',
    'phone_setting.ring_type': 'Тип мелодии',
    'static.auto_provision.custom.protect': 'Защита пользовательских настроек',
    'static.auto_provision.password': 'Пароль провижининга',
    'static.auto_provision.power_on': 'Провижининг при включении',
    'static.auto_provision.repeat.minutes': 'Интервал повтора (мин)',
    'static.auto_provision.server.url': 'URL сервера провижининга',
    'static.auto_provision.username': 'Логин провижининга',
    'static.auto_provision.weekly.enable': 'Еженедельный провижининг',
    'static.network.802_1x.identity': '802.1X: идентификатор',
    'static.network.802_1x.mode': '802.1X: режим',
    'static.network.ip_address_mode': 'Режим IP-адреса',
    'static.network.ipv6_enable': 'Включить IPv6',
    'static.network.primary_dns': 'Основной DNS',
    'static.network.secondary_dns': 'Дополнительный DNS',
    'static.network.static_dns_enable': 'Использовать статический DNS',
    'static.network.vlan.internet_port_enable': 'Включить VLAN',
    'static.network.vlan.internet_port_priority': 'Приоритет VLAN (CoS)',
    'static.network.vlan.internet_port_vid': 'ID VLAN',
    'static.sys.local_log.retention.enable': 'Хранение локальных логов',
    'static.syslog.level': 'Уровень syslog',
    'voice.handfree.spk_vol': 'Громкость громкой связи',
    'voice.handset.spk_vol': 'Громкость динамика трубки',
    'voice.ring_vol': 'Громкость звонка',
}

GROUP_LABELS_RU = {
    'Network': 'Сеть',
    'LDAP': 'LDAP',
    'Time': 'Время',
    'Auto Provision': 'Провижининг',
    'Phone Web UI': 'Веб-UI телефона',
    'Action URI': 'Action URI',
    'Action URL Events': 'События Action URL',
    'Features': 'Функции',
}


def humanize_key(key: str) -> str:
    """Грубое человекочитаемое имя из ключа cfg."""
    if not key:
        return key
    tail = key.split(".")[-1].replace("_", " ")
    # 802 1x -> 802.1X style bits left as-is from original
    return tail[:1].upper() + tail[1:] if tail else key


def param_label(key: str, lang: str = "ru") -> str:
    lang = (lang or "ru")[:2].lower()
    if lang == "ru":
        if key in PARAM_LABELS_RU:
            return PARAM_LABELS_RU[key]
        if key in PARAM_LABELS:
            # fallback EN known label if no RU yet
            return PARAM_LABELS[key]
        return humanize_key(key)
    return PARAM_LABELS.get(key) or humanize_key(key)


def group_label(name: str, lang: str = "ru") -> str:
    lang = (lang or "ru")[:2].lower()
    if lang == "ru":
        return GROUP_LABELS_RU.get(name, name)
    return name
