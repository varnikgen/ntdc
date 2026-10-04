from app.formutil import parse_json_field, parse_json_list, parse_json_dict


def test_parse_json_field_ok():
    assert parse_json_field('{"a": 1}', {}) == {"a": 1}
    assert parse_json_field("[1, 2]", []) == [1, 2]


def test_parse_json_field_bad():
    assert parse_json_field("not-json", {"x": 1}) == {"x": 1}
    assert parse_json_field(None, []) == []
    assert parse_json_field("", {}) == {}


def test_parse_json_list_and_dict():
    assert parse_json_list('["a"]') == ["a"]
    assert parse_json_list('{"a":1}') == []
    assert parse_json_dict('{"a":1}') == {"a": 1}
    assert parse_json_dict("[]") == {}
