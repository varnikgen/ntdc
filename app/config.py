"""Настройки приложения. Всё секретное — только из .env, дефолтов в проде нет."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": неизвестные переменные в .env не роняют старт
    # case_sensitive=True: NTDC_ADMIN_PASS и ntdc_admin_pass — разные имена
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "NTDC"  # UI brand
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = False  # True включает SQL-echo — в лог попадут SIP-пароли

    DATABASE_URL: str = "sqlite:///./data/ntdc.db"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # URL, который телефоны прописывают в auto_provision.server.url (без слэша в конце)
    PUBLIC_BASE_URL: str = "https://localhost"

    SECRET_KEY: str = ""  # для CSRF-cookie; минимум 16 символов

    NTDC_ADMIN_USER: str = "admin"
    NTDC_ADMIN_PASS: str = ""  # пустой / из чёрного списка → отказ стартовать

    # HTTP Basic на /provision. Те же учётки пишутся в глобальный cfg,
    # чтобы трубки ходили за конфигом повторно уже с паролем.
    PROVISION_AUTH_ENABLED: bool = True
    PROVISION_USER: str = "provision"
    PROVISION_PASS: str = ""
    # Заводской сброс: без Basic отдать только логин/пароль провижининга (не SIP).
    # false = строгий 401, трубка покажет Invalid provisioning credential.
    PROVISION_BOOTSTRAP: bool = True

    # Веб-пароль трубки (не admin). Пишется в security.user_password —
    # иначе после reset Yealink требует сменить заводской admin.
    PHONE_WEB_USER: str = "admin"
    PHONE_WEB_PASSWORD: str = ""

    # Общий секрет в Action URL: /actions/?token=...&mac=$mac
    ACTION_URI_TOKEN: str = ""
    # Создавать Phone при первом cfg-запросе / Action URL с неизвестным MAC
    AUTO_ENROLL: bool = True

    AUTOP_TIMEOUT: int = 5
    # Веб-UI Yealink почти всегда с самоподписанным сертификатом
    AUTOP_VERIFY_SSL: bool = False

    AUDIT_RETENTION_DAYS: int = 90
    OFFLINE_TIMEOUT_MINUTES: int = 5

    # Значение overwrite_mode в .boot:
    # 0 — локальные правки на трубке сохраняются (конфликты с сервером)
    # 1 — провижининг затирает локальные настройки (централизованное управление)
    BOOT_OVERWRITE_MODE: int = 1

    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_SECONDS: int = 60

    def validate_security(self) -> list[str]:
        """Фатальные ошибки конфигурации. Пустой список = можно стартовать."""
        errors: list[str] = []
        if not self.NTDC_ADMIN_PASS:
            errors.append(
                "NTDC_ADMIN_PASS is not set. Copy .env.example to .env and set a strong password."
            )
        # Эти значения уже светились в git — считаем их скомпрометированными.
        if self.NTDC_ADMIN_PASS in {"ChangeMe123!", "admin", "password", "Cgtwbfkbcbn01"}:
            errors.append(
                "NTDC_ADMIN_PASS is a known default/leaked value. Set a unique password."
            )
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 16:
            errors.append("SECRET_KEY must be set to a random string of at least 16 characters.")
        if self.PROVISION_AUTH_ENABLED and not self.PROVISION_PASS:
            errors.append(
                "PROVISION_AUTH_ENABLED=true requires PROVISION_PASS "
                "(or set PROVISION_AUTH_ENABLED=false for a lab-only bootstrap)."
            )
        if not self.ACTION_URI_TOKEN or len(self.ACTION_URI_TOKEN) < 8:
            errors.append("ACTION_URI_TOKEN must be set to a random string of at least 8 characters.")
        return errors

    @property
    def base_url(self) -> str:
        return self.PUBLIC_BASE_URL.rstrip("/")


settings = Settings()
