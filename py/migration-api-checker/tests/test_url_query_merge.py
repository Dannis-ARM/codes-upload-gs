"""Test URL query parsing and merging logic."""

from urllib.parse import urlparse, parse_qsl, urlunparse


def test_url_query_parsing():
    """Test that we can parse query params from URL."""
    # Simple case
    url = "http://example.com/api?param1=value1&param2=value2"
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    assert query_params == {"param1": "value1", "param2": "value2"}

    # With special characters
    url = "http://example.com/api?fields=[id,name]&filter=status:active"
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    assert query_params == {"fields": "[id,name]", "filter": "status:active"}

    # With dots
    url = "http://example.com/api?user.name=test&user.email=test@example.com"
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    assert query_params == {"user.name": "test", "user.email": "test@example.com"}


def test_query_merging_config_overrides_url():
    """Test that config params override URL params."""
    url_params = {"param1": "url_value", "param2": "url_value2"}
    config_params = {"param2": "config_value", "param3": "config_value3"}

    merged = {**url_params, **config_params}

    assert merged == {
        "param1": "url_value",
        "param2": "config_value",
        "param3": "config_value3"
    }


def test_manual_query_construction():
    """Test manual query string construction preserves special chars."""
    params = {
        "fields": "[id,name]",
        "filter": "status:active",
        "user.name": "test",
        "page": "1"
    }

    query_parts = []
    for k, v in params.items():
        if v is None:
            query_parts.append(f"{k}")
        else:
            query_parts.append(f"{k}={v}")
    final_query = "&".join(query_parts)

    assert final_query == "fields=[id,name]&filter=status:active&user.name=test&page=1"
