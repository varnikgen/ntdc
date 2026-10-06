"""Подключение к SQLite и аддитивные миграции колонок.

create_all() создаёт только отсутствующие таблицы и НЕ добавляет колонки
в уже существующие. Поэтому после обновления с 0.1.x вызываем run_migrations().
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # FastAPI крутит запросы в разных потоках; без этого флага SQLite ругается.
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,  # только в DEBUG: иначе SIP-пароли в логах
)

if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")       # чтение не блокирует запись
        cursor.execute("PRAGMA synchronous=NORMAL")     # компромисс скорость/надёжность
        cursor.execute("PRAGMA foreign_keys=ON")        # SQLite по умолчанию FK выключает
        cursor.execute("PRAGMA cache_size=-64000")      # 64 МБ кэша страниц
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Сессия на один HTTP-запрос. Depends(get_db) сам закроет её в finally."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Добавляет новые колонки в живую SQLite, не трогая данные.

    Если таблицы ещё нет (свежий create_all) — PRAGMA table_info пустой,
    ALTER пропускаем: create_all уже создал актуальную схему.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    statements = [
        ("phone_models", "ieee802_1x_md5_password", "ALTER TABLE phone_models ADD COLUMN ieee802_1x_md5_password VARCHAR"),
        ("phones", "admin_username", "ALTER TABLE phones ADD COLUMN admin_username VARCHAR(64) DEFAULT 'admin'"),
        ("phones", "admin_password", "ALTER TABLE phones ADD COLUMN admin_password VARCHAR(64) DEFAULT 'admin'"),
        ("phones", "override_exp_keys", "ALTER TABLE phones ADD COLUMN override_exp_keys BOOLEAN DEFAULT 0"),
        ("phones", "custom_exp_keys", "ALTER TABLE phones ADD COLUMN custom_exp_keys JSON"),
    ]

    with engine.begin() as conn:
        for table, column, ddl in statements:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {row[1] for row in rows}
            if existing and column not in existing:
                conn.execute(text(ddl))

        # Индексы для списков и фонового offline-скана (идемпотентно)
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_phones_status ON phones (status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_phones_last_seen ON phones (last_seen)"
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS phone_accounts (
                phone_id INTEGER NOT NULL,
                line_no INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                PRIMARY KEY (phone_id, line_no),
                FOREIGN KEY(phone_id) REFERENCES phones (id) ON DELETE CASCADE,
                FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE
            )
            """
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_phone_accounts_account_id ON phone_accounts (account_id)"
        ))
