"""Tests for DeepDiff-based comparator."""

from migration_checker.comparator import compare_responses, CompareOptions
from migration_checker.client import Response


def make_response(body, status_code=200):
    """Helper to create a Response object."""
    return Response(
        url="http://example.com",
        status_code=status_code,
        headers={},
        body=body,
        raw_body="",
        elapsed_seconds=0.1,
    )


class TestCompareResponses:
    """Tests for compare_responses function."""

    def test_identical_bodies_match(self):
        """Identical bodies should return match=True."""
        before = make_response({"data": [{"id": 1, "name": "test"}]})
        after = make_response({"data": [{"id": 1, "name": "test"}]})

        result = compare_responses(before, after)

        assert result.match is True
        assert result.diff == ""

    def test_different_bodies_no_match(self):
        """Different bodies should return match=False with diff."""
        before = make_response({"data": [{"id": 1, "name": "test"}]})
        after = make_response({"data": [{"id": 1, "name": "changed"}]})

        result = compare_responses(before, after)

        assert result.match is False
        assert "name" in result.diff

    def test_status_code_mismatch(self):
        """Different status codes should fail fast."""
        before = make_response({"ok": True}, status_code=200)
        after = make_response({"ok": True}, status_code=500)

        result = compare_responses(before, after)

        assert result.match is False
        assert "Status code mismatch" in result.diff

    def test_exclude_paths_works(self):
        """exclude_paths should ignore specified fields."""
        before = make_response({"data": {"id": 1, "timestamp": "2024-01-01"}})
        after = make_response({"data": {"id": 1, "timestamp": "2024-01-02"}})

        options = CompareOptions(exclude_paths=["root['data']['timestamp']"])
        result = compare_responses(before, after, options)

        assert result.match is True

    def test_exclude_paths_wildcard_works(self):
        """Wildcards in exclude_paths should work."""
        before = make_response({"data": [{"id": 1, "updatedAt": "old"}, {"id": 2, "updatedAt": "old"}]})
        after = make_response({"data": [{"id": 1, "updatedAt": "new"}, {"id": 2, "updatedAt": "new"}]})

        options = CompareOptions(exclude_paths=["root['data'][*]['updatedAt']"])
        result = compare_responses(before, after, options)

        assert result.match is True

    def test_exclude_regex_paths_works(self):
        """exclude_regex_paths should ignore matching paths."""
        before = make_response({"data": [{"id": 1, "createdAt": "old"}, {"id": 2, "createdAt": "old"}]})
        after = make_response({"data": [{"id": 1, "createdAt": "new"}, {"id": 2, "createdAt": "new"}]})

        options = CompareOptions(exclude_regex_paths=[r"root\['data'\]\[\d+\]\['createdAt'\]"])
        result = compare_responses(before, after, options)

        assert result.match is True

    def test_ignore_order_true(self):
        """ignore_order=True should treat reordered arrays as equal."""
        before = make_response({"data": [1, 2, 3]})
        after = make_response({"data": [3, 2, 1]})

        options = CompareOptions(ignore_order=True)
        result = compare_responses(before, after, options)

        assert result.match is True

    def test_ignore_order_false_default(self):
        """ignore_order=False (default) should detect reordered arrays."""
        before = make_response({"data": [1, 2, 3]})
        after = make_response({"data": [3, 2, 1]})

        options = CompareOptions(ignore_order=False)
        result = compare_responses(before, after, options)

        assert result.match is False

    def test_ignore_numeric_type_changes_true_default(self):
        """ignore_numeric_type_changes=True (default) should treat int and float as equal."""
        before = make_response({"count": 1})
        after = make_response({"count": 1.0})

        result = compare_responses(before, after)

        assert result.match is True

    def test_ignore_numeric_type_changes_false(self):
        """ignore_numeric_type_changes=False should detect int vs float difference."""
        before = make_response({"count": 1})
        after = make_response({"count": 1.0})

        options = CompareOptions(ignore_numeric_type_changes=False)
        result = compare_responses(before, after, options)

        assert result.match is False
