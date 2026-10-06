"""Тесты импорта FreePBX Extensions CSV → SIP-аккаунты."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.models import Account
from app.services.freepbx_csv_import import parse_freepbx_csv, import_accounts_from_csv

FIXTURE = Path(__file__).parent / "fixtures_extensions_test.csv"


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_parse_fixture_csv():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = parse_freepbx_csv(text)
    assert len(rows) == 2
    assert rows[0]["username"] == "10301"
    assert rows[0]["password"] == "T103001t"  # из secret, не password
    assert rows[0]["name"] == "KashirskiiVI"
    assert rows[0]["display_name"] == "KashirskiiVI"
    assert rows[0]["transport"] == "udp"  # пустое → udp

    assert rows[1]["username"] == "10302"
    assert rows[1]["password"] == "T103002t"
    assert rows[1]["name"] == "YakimchukGG"


def test_parse_secret_fallback_to_password():
    csv_text = "extension,password,name,secret\n101,pass101,Alice,\n102,,Bob,sec102\n"
    rows = parse_freepbx_csv(csv_text)
    assert rows[0]["password"] == "pass101"
    assert rows[1]["password"] == "sec102"


def test_parse_skips_empty_extension():
    csv_text = "extension,secret,name\n,secret1,X\n103,secret2,Y\n"
    rows = parse_freepbx_csv(csv_text)
    assert len(rows) == 1
    assert rows[0]["username"] == "103"


def test_import_create(db: Session):
    text = FIXTURE.read_text(encoding="utf-8")
    result = import_accounts_from_csv(db, text, sip_server="pbx.test.local", sip_port=5060)
    assert result["total"] == 2
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["skipped"] == 0
    assert not result["errors"]

    a1 = db.query(Account).filter(Account.username == "10301").one()
    assert a1.name == "KashirskiiVI"
    assert a1.password == "T103001t"
    assert a1.sip_server == "pbx.test.local"
    assert a1.sip_port == 5060
    assert a1.transport == "udp"
    assert a1.display_name == "KashirskiiVI"


def test_import_update_existing(db: Session):
    text = FIXTURE.read_text(encoding="utf-8")
    # первый проход — create
    import_accounts_from_csv(db, text, sip_server="old.server", sip_port=5060)
    # второй — update (в т.ч. server/port/name)
    csv2 = (
        "extension,secret,name,description,transport\n"
        "10301,NEWPASS,NewName,New Display,tcp\n"
    )
    result = import_accounts_from_csv(db, csv2, sip_server="new.server", sip_port=5061)
    assert result["created"] == 0
    assert result["updated"] == 1

    a = db.query(Account).filter(Account.username == "10301").one()
    assert a.password == "NEWPASS"
    assert a.name == "NewName"
    assert a.display_name == "New Display"
    assert a.sip_server == "new.server"
    assert a.sip_port == 5061
    assert a.transport == "tcp"


def test_import_update_keeps_password_if_empty(db: Session):
    import_accounts_from_csv(
        db,
        "extension,secret,name\n200,KEEPME,User200\n",
        sip_server="s",
    )
    result = import_accounts_from_csv(
        db,
        "extension,secret,name\n200,,User200upd\n",
        sip_server="s2",
    )
    assert result["updated"] == 1
    a = db.query(Account).filter(Account.username == "200").one()
    assert a.password == "KEEPME"
    assert a.name == "User200upd"
    assert a.sip_server == "s2"


def test_import_skip_create_without_password(db: Session):
    result = import_accounts_from_csv(
        db,
        "extension,secret,name\n300,,NoPass\n",
        sip_server="s",
    )
    assert result["created"] == 0
    assert result["skipped"] == 1
    assert any("300" in e for e in result["errors"])
    assert db.query(Account).filter(Account.username == "300").first() is None


def test_import_requires_sip_server(db: Session):
    result = import_accounts_from_csv(db, "extension,secret,name\n1,p,n\n", sip_server="")
    assert result["errors"]
    assert result["created"] == 0


def test_http_import_csv(client, admin_headers):
    text = FIXTURE.read_text(encoding="utf-8")
    r = client.post(
        "/accounts/import-csv",
        data={"sip_server": "http-pbx.local", "sip_port": "5070"},
        files={"file": ("extensions.csv", text.encode("utf-8"), "text/csv")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "success"
    # create или update — БД общая с unit-тестами в рамках session
    assert data["result"]["created"] + data["result"]["updated"] == 2

    db = SessionLocal()
    try:
        a = db.query(Account).filter(Account.username == "10301").one()
        assert a.sip_server == "http-pbx.local"
        assert a.sip_port == 5070
        assert a.password == "T103001t"
    finally:
        db.close()


def test_http_import_requires_server(client, admin_headers):
    r = client.post(
        "/accounts/import-csv",
        data={"sip_server": ""},
        files={"file": ("e.csv", b"extension,secret\n1,p\n", "text/csv")},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_http_import_requires_file(client, admin_headers):
    r = client.post(
        "/accounts/import-csv",
        data={"sip_server": "x"},
        headers=admin_headers,
    )
    assert r.status_code == 400
