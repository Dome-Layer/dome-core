import pytest

from dome_core.json_utils import parse_json_response, strip_json_fences


def test_strip_plain_json():
    assert strip_json_fences('{"a": 1}') == '{"a": 1}'


def test_strip_fenced_json():
    text = '```json\n{"a": 1}\n```'
    assert strip_json_fences(text) == '{"a": 1}'


def test_strip_fenced_no_lang():
    text = '```\n{"a": 1}\n```'
    assert strip_json_fences(text) == '{"a": 1}'


def test_strip_fenced_multiline():
    text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
    result = strip_json_fences(text)
    assert '"a": 1' in result
    assert '"b": 2' in result


def test_strip_fenced_no_trailing():
    text = '```json\n{"a": 1}'
    result = strip_json_fences(text)
    assert result == '{"a": 1}'


def test_parse_json_response_clean():
    assert parse_json_response('{"x": 42}') == {"x": 42}


def test_parse_json_response_fenced():
    assert parse_json_response('```json\n{"x": 42}\n```') == {"x": 42}


def test_parse_json_response_invalid():
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_json_response("not json at all")
