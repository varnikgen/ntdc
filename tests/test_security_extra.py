from app.security import detect_model_from_ua, hash_password, verify_password
from app.services.cfg_import import ip_from_filename, detect_model_from_filename


def test_detect_model():
    assert detect_model_from_ua("Yealink SIP-T46U 108.87.14.1 24:9a:d8:6e:9d:88") == "T46U"


def test_password_hash():
    h = hash_password("secret-pass-99")
    assert verify_password("secret-pass-99", h)
    assert not verify_password("wrong", h)


def test_ip_and_model_from_export_name():
    name = "10.30.16.10_44DBD222CF31_T31P-all.cfg"
    assert ip_from_filename(name) == "10.30.16.10"
    assert detect_model_from_filename(name) == "T31P"
