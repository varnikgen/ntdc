from app.database import SessionLocal
from app.models import Phone, Account, PhoneAccount
from app.phone_accounts import set_account_ids, get_account_ids, detach_account


def test_set_get_account_ids():
    db = SessionLocal()
    try:
        acc = Account(
            name="t1", sip_server="sip.test", username="u_test_pa_1",
            password="secret", display_name="T",
        )
        db.add(acc)
        db.flush()
        phone = Phone(mac="AABBCCDDEE01", status="offline", account_ids=[])
        db.add(phone)
        db.flush()
        set_account_ids(db, phone, [acc.id])
        db.commit()
        db.refresh(phone)
        assert get_account_ids(db, phone) == [acc.id]
        rows = db.query(PhoneAccount).filter(PhoneAccount.phone_id == phone.id).all()
        assert len(rows) == 1 and rows[0].line_no == 1
        # cleanup
        detach_account(db, acc.id)
        db.delete(phone)
        db.delete(acc)
        db.commit()
    finally:
        db.close()
