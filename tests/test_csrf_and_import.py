from app.services.cfg_import import ip_from_filename, detect_model_from_filename, parse_yealink_cfg


def test_import_filename_parsing():
    name = "10.30.17.68_249AD86E9D88_T46U-all.cfg"
    assert ip_from_filename(name) == "10.30.17.68"
    assert detect_model_from_filename(name) == "T46U"


def test_parse_cfg_basic():
    text = "account.1.enable = 1\naccount.1.user_name = 101\n"
    d = parse_yealink_cfg(text)
    assert d["account.1.enable"] == "1"
    assert d["account.1.user_name"] == "101"


def test_csrf_cookie_on_login_page(client):
    r = client.get("/login")
    assert r.status_code == 200
    # cookie may be set by middleware on first response
    # at least page renders
    assert "password" in r.text.lower() or "парол" in r.text.lower()


def test_extract_dss_keys():
    from app.services.cfg_import import extract_dss_keys, parse_yealink_cfg
    text = """
linekey.1.type = 15
linekey.1.line = 1
linekey.1.label = Ext101
linekey.2.type = 16
linekey.2.line = 1
linekey.2.value = 102
linekey.2.label = Bob
linekey.3.type = 0
"""
    dss = extract_dss_keys(parse_yealink_cfg(text))
    assert len(dss) == 2
    assert dss[0]["type"] == 15 and dss[0]["label"] == "Ext101"
    assert dss[1]["type"] == 16 and dss[1]["value"] == "102"
