from app.security import (
    extract_mac,
    normalize_mac,
    quote_cfg,
    constant_time_equals,
    detect_model_from_ua,
)
from app.phone_ip import pick_phone_ip, is_phone_ip, is_container_ip


def test_normalize_mac_strips_separators():
    assert normalize_mac("00:15:65:c1:87:25") == "001565C18725"
    assert normalize_mac("001565c18725") == "001565C18725"
    assert normalize_mac("bad") is None


def test_extract_mac_from_yealink_ua_does_not_glue_firmware():
    ua = "Yealink SIP-T46U 108.87.14.1 24:9a:d8:6e:9d:88"
    assert extract_mac(ua, "") == "249AD86E9D88"


def test_extract_mac_from_query():
    assert extract_mac("", "24-9a-d8-6e-9d-88") == "249AD86E9D88"


def test_quote_cfg_special_chars():
    assert quote_cfg("simple") == "simple"
    assert quote_cfg("p@ss word") == "p@ss word"
    assert quote_cfg("cn=admin,dc=bsmuk,dc=ru") == "cn=admin,dc=bsmuk,dc=ru"
    assert quote_cfg("cn sn") == "cn sn"
    assert quote_cfg("foo#bar") == '"foo#bar"'
    assert quote_cfg('a"b') == r'"a\"b"'
    assert quote_cfg(True) == "1"
    assert quote_cfg(False) == "0"


def test_constant_time_equals():
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")


def test_pick_phone_ip_ignores_podman_nat():
    assert is_container_ip("10.89.0.3")
    assert is_phone_ip("10.30.17.68")
    assert pick_phone_ip("10.30.17.68", "10.89.0.3", "10.89.0.3") == "10.30.17.68"
    assert pick_phone_ip(None, "10.89.0.3", "10.30.17.68") == "10.30.17.68"
    assert pick_phone_ip(None, "10.30.17.68", None) is None  # TCP-источник не доверяем
    assert pick_phone_ip(None, "10.89.0.3", "10.89.0.3") is None
    assert pick_phone_ip("$ip", "10.89.0.3", None) is None


def test_detect_model_from_ua():
    assert detect_model_from_ua("Yealink SIP-T46U 108.87.14.1 24:9a:d8:6e:9d:88") == "T46U"
    assert detect_model_from_ua("Yealink SIP-T54W 96.86.0.74") == "T54W"
    assert detect_model_from_ua("Yealink SIP-T48U 108.86.0.20") == "T48U"
    assert detect_model_from_ua("Yealink W70B 146.85.0.5") == "W70B"
    assert detect_model_from_ua("Yealink VP-T49G 51.80.0.100") in {"T49G", "VP-T49G"}
    assert detect_model_from_ua("Mozilla/5.0") is None
    assert detect_model_from_ua("") is None

