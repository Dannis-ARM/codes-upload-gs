"""Test ignore_fields functionality works correctly."""

from migration_checker.comparator import compare_responses
from migration_checker.client import Response


def test_ignore_fields_top_level():
    """Test that top-level fields are ignored."""
    before = Response(
        url="http://example.com/before",
        status_code=200,
        headers={},
        body={"id": 123, "name": "Test", "timestamp": "2024-01-01"},
        raw_body="",
        elapsed_seconds=0.1,
    )
    after = Response(
        url="http://example.com/after",
        status_code=200,
        headers={},
        body={"id": 456, "name": "Test", "timestamp": "2024-01-02"},
        raw_body="",
        elapsed_seconds=0.1,
    )

    # Without ignore_fields - should fail because id and timestamp differ
    result = compare_responses(before, after, ignore_fields=[])
    assert result.match is False

    # With ignore_fields - should pass
    result = compare_responses(before, after, ignore_fields=["id", "timestamp"])
    assert result.match is True


def test_ignore_fields_nested():
    """Test that nested fields are ignored."""
    before = Response(
        url="http://example.com/before",
        status_code=200,
        headers={},
        body={"data": {"id": 1, "value": "same", "updatedAt": "2024-01-01"}},
        raw_body="",
        elapsed_seconds=0.1,
    )
    after = Response(
        url="http://example.com/after",
        status_code=200,
        headers={},
        body={"data": {"id": 2, "value": "same", "updatedAt": "2024-01-02"}},
        raw_body="",
        elapsed_seconds=0.1,
    )

    result = compare_responses(before, after, ignore_fields=["data.id", "data.updatedAt"])
    assert result.match is True


def test_ignore_fields_wildcard_array():
    """Test that wildcard in array paths works."""
    before = Response(
        url="http://example.com/before",
        status_code=200,
        headers={},
        body={
            "items": [
                {"id": 1, "name": "A", "updatedAt": "2024-01-01"},
                {"id": 2, "name": "B", "updatedAt": "2024-01-01"},
            ]
        },
        raw_body="",
        elapsed_seconds=0.1,
    )
    after = Response(
        url="http://example.com/after",
        status_code=200,
        headers={},
        body={
            "items": [
                {"id": 101, "name": "A", "updatedAt": "2024-01-02"},
                {"id": 102, "name": "B", "updatedAt": "2024-01-02"},
            ]
        },
        raw_body="",
        elapsed_seconds=0.1,
    )

    result = compare_responses(before, after, ignore_fields=["items[*].id", "items[*].updatedAt"])
    assert result.match is True


def test_ignore_fields_partial_mismatch():
    """Test that only ignored fields are skipped, other mismatches still fail."""
    before = Response(
        url="http://example.com/before",
        status_code=200,
        headers={},
        body={"id": 1, "name": "Test", "timestamp": "2024-01-01"},
        raw_body="",
        elapsed_seconds=0.1,
    )
    after = Response(
        url="http://example.com/after",
        status_code=200,
        headers={},
        body={"id": 2, "name": "Changed", "timestamp": "2024-01-02"},
        raw_body="",
        elapsed_seconds=0.1,
    )

    # Only ignore id and timestamp - name still differs
    result = compare_responses(before, after, ignore_fields=["id", "timestamp"])
    assert result.match is False
    assert "name" in result.diff
