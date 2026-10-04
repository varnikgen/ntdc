"""ORM-модели. JSON-поля (account_ids, dss_keys, settings) без FK —
целостность поддерживаем в роутерах при удалении."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class PhoneModel(Base):
    """Линейка аппаратов (T46U, T31G, …). Имя совпадает с $PN Yealink."""
    __tablename__ = "phone_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  # "T46U"

    max_dss_keys = Column(Integer, default=27)
    max_accounts = Column(Integer, default=16)

    firmware_url = Column(String, nullable=True)

    ieee802_1x_enable = Column(Boolean, default=False)
    ieee802_1x_identity = Column(String, default="yealink")
    ieee802_1x_mode = Column(Integer, default=2)  # 0=EAP-TLS, 2=EAP-MD5, 3=PEAP, 5=TTLS
    ieee802_1x_md5_password = Column(String, nullable=True)
    ieee802_1x_root_cert_url = Column(String, nullable=True)
    ieee802_1x_client_cert_url = Column(String, nullable=True)
    ieee802_1x_upload_mode = Column(Integer, default=0)

    # Произвольные ключи модели → попадают в $PN.cfg как есть
    default_config = Column(JSON, default=dict)

    phones = relationship("Phone", back_populates="model")


class Account(Base):
    """SIP-аккаунт. Один аккаунт может висеть на нескольких трубках."""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    sip_server = Column(String, nullable=False)
    sip_port = Column(Integer, default=5060)
    transport = Column(String, default="udp")  # udp | tcp | tls
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # в cfg уходит plaintext — Yealink иначе не умеет
    display_name = Column(String)

    # DSS по умолчанию; трубки без override_dss_keys наследуют этот список
    dss_keys = Column(JSON, default=list)

    phones = relationship("Phone", back_populates="primary_account")


class Phone(Base):
    """Конкретное устройство. mac — 12 hex без разделителей, UPPERCASE."""
    __tablename__ = "phones"

    id = Column(Integer, primary_key=True, index=True)
    mac = Column(String(12), unique=True, index=True, nullable=False)
    # FK на name, не на id: boot-файл Yealink запрашивает $PN.cfg по имени модели
    model_name = Column(String, ForeignKey("phone_models.name"), nullable=True)

    # Учётки веб-UI трубки, только для AutoP push. В cfg не пишутся.
    admin_username = Column(String(64), default="admin")
    admin_password = Column(String(64), default="admin")

    # Порядок = номер линии: index 0 → account.1.*, index 1 → account.2.*
    account_ids = Column(JSON, default=list)
    primary_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    ip_address = Column(String, nullable=True)  # обновляется из Action URL
    status = Column(String, default="offline")  # online | offline | dnd | unregistered
    last_seen = Column(DateTime, default=datetime.utcnow)

    override_dss_keys = Column(Boolean, default=False)
    custom_dss_keys = Column(JSON, nullable=True)
    custom_config = Column(JSON, default=dict)  # индивидуальные ключи → $MAC.cfg

    model = relationship("PhoneModel", back_populates="phones")
    primary_account = relationship(
        "Account", back_populates="phones", foreign_keys=[primary_account_id]
    )


class GlobalConfig(Base):
    """Единственная строка: словарь ключей для y000000000000.cfg."""
    __tablename__ = "global_config"

    id = Column(Integer, primary_key=True, index=True)
    settings = Column(JSON, default=dict)


class AuditLog(Base):
    """Журнал действий админки и auto-enroll. Чистится фоновой задачей."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String, nullable=False)  # CREATE_PHONE, UPDATE_ACCOUNT, AUTO_ENROLL, …
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer)
    user = Column(String, default="system")
    details = Column(Text)

class AdminUser(Base):
    """Пользователь веб-админки. Роли: admin | operator | viewer."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="operator", nullable=False)  # admin | operator | viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

