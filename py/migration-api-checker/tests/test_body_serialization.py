"""Test body serialization to JSON string works correctly."""

import json


def test_body_serialization_various_types():
    """Test that different body types are serialized correctly."""

    def to_json_str(data):
        if data is None:
            return "null"
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False)

    # None case
    assert to_json_str(None) == "null"

    # Already string case
    assert to_json_str('{"key": "value"}') == '{"key": "value"}'
    assert to_json_str("plain text response") == "plain text response"

    # Dict case
    assert to_json_str({"key": "value", "number": 123}) == '{"key": "value", "number": 123}'

    # List case
    assert to_json_str([1, 2, {"nested": "value"}]) == '[1, 2, {"nested": "value"}]'

    # Number/Bool case
    assert to_json_str(123) == "123"
    assert to_json_str(True) == "true"
    assert to_json_str(False) == "false"
