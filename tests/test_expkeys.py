
from app.services.linekeys import render_expkeys_block


def test_render_expkeys_empty():
    assert render_expkeys_block(None) == ""
    assert render_expkeys_block([]) == ""


def test_render_expkeys_basic():
    keys = [
        {"module": 1, "key": 2, "type": 16, "account": 1, "value": "10301", "extension": "", "label": "Kash"},
        {"module": 1, "key": 1, "type": 13, "account": 1, "value": "100", "extension": "", "label": "Speed"},
    ]
    text = render_expkeys_block(keys)
    assert "expansion_module.1.key.1.type = 13" in text
    assert "expansion_module.1.key.1.value = 100" in text
    assert "expansion_module.1.key.2.type = 16" in text
    assert "expansion_module.1.key.2.label = Kash" in text
    # sorted by module, key
    assert text.index("key.1") < text.index("key.2")


def test_render_expkeys_type_zero_line():
    text = render_expkeys_block([{"module": 1, "key": 1, "type": 0, "account": 5, "value": "", "extension": "", "label": ""}])
    assert "type = 0" in text
    assert "line = 0" in text
